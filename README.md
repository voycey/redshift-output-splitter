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
<pre>
<b>-q</b> | <b>--queue</b>, 'Name of the Queue to watch', required=True
<b>-d</b> | <b>--destination</b>, 'Destination bucket', required=True
<b>-i</b> | <b>--input</b>, 'Input File Type', default='gz'
<b>-c</b> | <b>--chunk</b>, 'Chunk Size to split file', default='100M'
<b>-r</b> | <b>--region</b>, 'AWS Region of the bucket', default='us-west-2'
<b>-f</b> | <b>--filename</b>, 'Filename Prefix', default='redshift'
<b>-z</b> | <b>--zip</b>, 'Compression output to use, default='bzip2'
</pre>

Example:

	python redshift-splitter -q my-sqs-queue -d my-output-bucket

## Example Output


	https://us-west-2.queue.amazonaws.com/9999999999999/redshift-splitting
	= Loading Queue JSON =
	= Details from SQS =
	Bucket: my-bucket-name
	File: temp/redshift000.gz
	Size: 113859318
	= Retrieving S3 file =
	= Unzipping S3 file =
	= Splitting file into chunks =
	= Adding Headers to Splits =
	= Rezipping files =
	= Deleting source files =
	= Creating destination folder =
	= Uploading files =

	File uploaded to https://s3.us-west-2.amazonaws.com/my-bucket-name/00000000-000000/redshift-part-00.bz2
	...
	File uploaded to https://s3.us-west-2.amazonaws.com/my-bucket-name/00000000-00000/redshift-part-27.bz2

	= Cleaning up =
	= Marking complete in SQS =

## Notes about Headers
Redshift doesn't offer an option to add headers to the output, there are various hacks around this (none of which seem very pleasant to be honest) so I have included a couple of options in this script should you require them:
<pre>
	<b>-H</b> or <b>---headers</b> This tells the script that there are headers in the first row of the file, this will then take that first line, and prepend it to every chunk created

	<b>--HL</b>- or <b>---header-list</b>-  This takes a quoted list of column names as its argument (e.g: "list | of | headers") and then prepends it to the file before chunking; If used with -H above it will write this header line to each chunk (be careful that the file doesn't already contain a header line direct from Redshift in this case)
</pre>
## Examples
	python redshift-splitter.py -q redshift-splitting -d redshift-processed

Simplest example: will monitor the ``redshift-splitting`` SQS queue for an S3 file and output it in 200MB chunks (pre-compressed) to the ``redshift-processed`` bucket

	python redshift-splitter.py -q redshift-splitting -d redshift-processed -c 50 -H -HL "utc_timestamp | first_name | last_name | address1 | city | ip_address"

Runs against the queue called ``redshift-splitting`` into destination bucket ``redshift-processed`` with a pre-compressed chunk size of 50MB

## Gotchas

If the file size is greater than 6.8GB Redshift automatically splits it, as such 2 messages will be posted to the SQS queue and 2 sets of data will be processed. I have not tested this yet as I dont have any data that is > 6.8GB compresed but as the script outputs it to a date folder (including minutes and seconds) it should handle it fine.
