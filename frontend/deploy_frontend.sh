#!/bin/bash
BUCKET="your-s3-bucket-name"
aws s3 cp frontend/index.html s3://$BUCKET/index.html \
  --content-type "text/html" \
  --cache-control "no-cache"
echo "Frontend deployed to s3://$BUCKET"