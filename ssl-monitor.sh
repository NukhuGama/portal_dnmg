#!/bin/bash

# SSL Certificate Monitoring Script
# Checks certificate expiry and sends alerts if renewal fails
# Run via cron to get periodic notifications

DOMAIN="dnmg.gov.tl"
CERT_PATH="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
ALERT_EMAIL="itsupport@dnmg.gov.tl"
ALERT_DAYS=30
LOG_FILE="/var/log/ssl-monitor.log"

# Colors for terminal output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo "[$(date '+%Y-%m-%d %H:%M:%S')] SSL Certificate Monitor Started" >> $LOG_FILE

# Check if certificate exists
if [ ! -f "$CERT_PATH" ]; then
    echo -e "${RED}✗ Certificate not found: $CERT_PATH${NC}"
    echo "ERROR: Certificate not found at $CERT_PATH" >> $LOG_FILE
    exit 1
fi

# Get expiry date
EXPIRY_DATE=$(openssl x509 -enddate -noout -in "$CERT_PATH" | cut -d= -f2)
EXPIRY_EPOCH=$(date -d "$EXPIRY_DATE" +%s)
NOW_EPOCH=$(date +%s)
DAYS_LEFT=$(( ($EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Certificate check for: $DOMAIN" >> $LOG_FILE
echo "Expiry date: $EXPIRY_DATE" >> $LOG_FILE
echo "Days until expiry: $DAYS_LEFT" >> $LOG_FILE

# Terminal output
echo -e "Domain: $DOMAIN"
echo -e "Expiry date: $EXPIRY_DATE"
echo -e "Days until expiry: $DAYS_LEFT"

# Check expiry status
if [ $DAYS_LEFT -lt 0 ]; then
    echo -e "${RED}✗ CRITICAL: Certificate has expired!${NC}"
    echo "ALERT: Certificate expired on $EXPIRY_DATE" >> $LOG_FILE
    echo "CRITICAL: Certificate has expired on $EXPIRY_DATE" | mail -s "🚨 CRITICAL: SSL Certificate Expired - $DOMAIN" $ALERT_EMAIL
    exit 1

elif [ $DAYS_LEFT -lt $ALERT_DAYS ]; then
    echo -e "${YELLOW}⚠ WARNING: Certificate expires in $DAYS_LEFT days${NC}"
    echo "WARNING: Certificate expires in $DAYS_LEFT days ($EXPIRY_DATE)" >> $LOG_FILE
    echo "WARNING: Certificate for $DOMAIN expires in $DAYS_LEFT days ($EXPIRY_DATE). Auto-renewal may have failed." | mail -s "⚠ WARNING: SSL Certificate Expiring Soon - $DOMAIN" $ALERT_EMAIL

elif [ $DAYS_LEFT -lt 7 ]; then
    echo -e "${YELLOW}⚠ NOTICE: Certificate expires in $DAYS_LEFT days${NC}"
    echo "NOTICE: Certificate expires soon: $DAYS_LEFT days" >> $LOG_FILE

else
    echo -e "${GREEN}✓ Certificate is valid${NC}"
    echo "OK: Certificate is valid" >> $LOG_FILE
fi

# Check renewal status
echo ""
echo "Renewal status:"
certbot certificates --authenticator nginx 2>&1 | grep -A2 "dnmg.gov.tl"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] SSL Certificate Monitor Completed" >> $LOG_FILE
