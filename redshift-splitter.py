import os
import json
import boto3
import gzip
import argparse
import shutil

from datetime import datetime

# Handle Arguments
parser = argparse.ArgumentParser(description='Watch an SQS Queue and process redshift files as they are exported - split them and then write them somewhere else')
parser.add_argument('-q','--queue', help='Name of the Queue to watch', required=True)
parser.add_argument('-d','--destination', help='Destination bucket', required=True)
parser.add_argument('-i','--input', help='Input File Type', default='gz')
parser.add_argument('-c','--chunk', help='Chunk Size to split file', default='100M')
parser.add_argument('-r','--region', help='AWS Region of the bucket', default='us-west-2')
parser.add_argument('-f','--filename', help='Filename Prefix', default='redshift')
parser.add_argument('-z','--zip', help='Compression output to use (uses <command> * so must support this)', default='bzip2')
args = vars(parser.parse_args())

# Get the service resource
sqs = boto3.resource('sqs')
s3 = boto3.resource('s3')

# Hard code to date folder to prevent warnings
# If you change this sanity check rmtree below to make sure you cant delete root
folder = datetime.now().strftime("%Y%m%d-%H%M%S")
redshift_folder = folder

if args['zip'] == 'bzip2':
	zout = '.bz2'
else:
	zout = 'gz'

if args['input'] == 'bzip2':
	zin = '.bz2'
else:
	zin = '.gz'

fullfilenamein = args['filename'] + zin
fullfilenameout = args['filename'] + zout


# Get the queue.
queue = sqs.get_queue_by_name(QueueName=args['queue'])

# Function to sync multiple files to S3 bucket
def sync_to_s3(target_dir, aws_region=args['region'], bucket_name=args['destination'], folder=''):
	if not os.path.isdir(target_dir):
		raise ValueError('target_dir %r not found.' % target_dir)

	s3 = boto3.resource('s3', region_name=args['region'])
	
	try:
		s3.create_bucket(Bucket=bucket_name,
			CreateBucketConfiguration={'LocationConstraint': args['region']})
	except Exception:
		pass

	for args['filename'] in os.listdir(target_dir):
		s3.Object(bucket_name, folder + '/' + args['filename']).put(Body=open(os.path.join(target_dir, args['filename']), 'rb'))

		print('File uploaded to https://s3.%s.amazonaws.com/%s/%s' % (
			args['region'], bucket_name, args['filename']))

# Print queue for debugging
print(queue.url)

# Process messages by printing out body and optional author name
for message in queue.receive_messages(MaxNumberOfMessages=1,WaitTimeSeconds=10):
	print("= Loading Queue JSON =")
	js = json.loads(message.body)

	bucket = js['Records'][0]['s3']['bucket']['name']
	key = js['Records'][0]['s3']['object']['key']

	print("= Details from SQS =")
	print("Bucket: " + bucket)
	print("File: " + key)

	if not os.path.exists(folder):
		os.makedirs(folder)

	print("= Retrieving S3 file =")

	# Download file here to local storage
	s3.meta.client.download_file(bucket, key, folder + '/' + fullfilenamein)

	os.chdir(folder)

	print("= Unzipping S3 file =")

	# Unzip all chunks
	if args['input'] == 'bzip2':
		os.system('bunzip2 ' + fullfilenamein)
	else:
		os.system('gunzip ' + fullfilenamein)
	
	print("= Splitting file into chunks =")
	
	# Split into 100MB chunks
	os.system('split -d -b ' + args['chunk'] + ' ' + args['filename'] + ' ' + args['filename'] + '-part-')

	print("= Rezipping files =")
	
	# Zip all chunks
	if args['zip'] == 'bzip2':
		os.system('bzip2 *part*')
	else:
		os.system('gzip *part*')
	
	print("= Deleting source files =")

	# Delete original file
	os.remove(args['filename'])

	# Re-upload

	print("= Creating destination folder =")

	response = s3.meta.client.put_object(
		Bucket=args['destination'],
		Body='',
		Key=redshift_folder + '/'
	)

	# Go back up one level
	os.chdir("..")

	print("= Uploading files =")

	# Upload the files to 
	sync_to_s3(folder, args['region'], args['destination'], redshift_folder)

	print("= Cleaning up =")

	shutil.rmtree(folder)
	os.listdir('.')

	print("= Marking complete in SQS =")

	message.delete()
