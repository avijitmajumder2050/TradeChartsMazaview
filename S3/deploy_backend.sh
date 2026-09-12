#!/bin/bash
EC2_HOST="15.207.151.67"
EC2_USER="ec2-user"
KEY="~/.ssh/your-key.pem"

ssh -i $KEY $EC2_USER@$EC2_HOST << 'REMOTE'
  cd /app/TradeChartsMazaview/backend
  docker build -t chart-api .
  docker stop chart-api 2>/dev/null || true
  docker rm   chart-api 2>/dev/null || true
  docker run -d -p 5000:5000 --name chart-api \
    --restart unless-stopped chart-api
REMOTE
echo "Backend deployed to EC2"