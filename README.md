[![Github All Releases](https://img.shields.io/github/downloads/voycey/redshift-output-splitter/total.svg)]()
[![GitHub contributors](https://img.shields.io/github/contributors/voycey/redshift-output-splitter.svg)]()


# Redshift output / unload splitter
Redshift is fantastic, but it doesn't support splitting the final unloaded file(s) into customisable size segments (as of Apr 2017 anyway), your choices are to leave parallel on and get a file per node, or turn parallel off and get one mega file.

We do the latter and unfortunately when shipping out the data there is often a filesize limit of what can be ingested, and it is really no fun having to download a 25GB archive (that unzips to a 200GB Text file) as you cant process files directly on S3. So, we created this!

## How does this work?
It basically monitors an SQS queue for a notification from S3 that a new file has been added, at which point it downloads it your server (ideally in the same region so it's fast), at which point it unzips, chops, re-zips and uploads it to your destination bucket - all hands free.

## Why do it this way?
Well, in our case the files created were too large for Lambda (it has a 512MB space limit), AWS Data Pipelines are a massive pain in the ass to get configured correctly and to be honest this seemed like the shortest route to Rome.

## AWS Setup

 1. Create an SQS queue
 2. Create a trigger on the bucket you want to monitor for new files to be added to, specify the SQS queue you created above
 3. Ensure that when you UNLOAD in Redshift you specify this bucket

## Script Installation
 1. Clone this repo to a location of your choice on the server you want to process the file on
 2.  Setup a cron job to run this as often as you want

## Syntax
The following arguments are accepted by this script:

    * **-q** | **--queue**, 'Name of the Queue to watch', required=True
    * **-d** | **--destination**, 'Destination bucket', required=True
    * **-i** | **--input**, 'Input File Type', default='gz'
    * **-c** | **--chunk**, 'Chunk Size to split file', default='100M'
    * **-r** | **--region**, 'AWS Region of the bucket', default='us-west-2'
    * **-f** | **--filename**, 'Filename Prefix', default='redshift'
    * **-z** | **--zip**, 'Compression output to use, default='bzip2'

Example:

	python redshift-splitter -q my-sqs-queue -d my-output-bucket

## Example Output

	
	https://us-west-2.queue.amazonaws.com/9999999999999/redshift-splitting
	= Loading Queue JSON =
	= Details from SQS =
	Bucket: my-bucket-name
	File: temp/redshift000.gz
	= Retrieving S3 file =
	= Unzipping S3 file =
	= Splitting file into chunks =
	= Rezipping files =
	= Deleting source files =
	= Creating destination folder =
	= Uploading files =
	File uploaded to https://s3.us-west-2.amazonaws.com/my-bucket-name/00000000-000000/redshift-part-00.bz2
	...
	File uploaded to https://s3.us-west-2.amazonaws.com/my-bucket-name/00000000-00000/redshift-part-27.bz2
	= Marking complete in SQS =
	= Cleaning up =
