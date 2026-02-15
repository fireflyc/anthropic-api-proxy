#!/bin/bash

# Color Definitions
GREEN='\033[0;32m'
YELLOW='\033[1;33m' # Fixed: Added the \033[ prefix
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

CONFIG_FILE="$HOME/.claude/settings.json"
BACKUP_FILE="${CONFIG_FILE}.bak"

# Helper functions for logging
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check for jq dependency
if ! command -v jq &> /dev/null; then
    log_error "'jq' is not installed. Please install it first."
    exit 1
fi

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    log_error "Configuration file not found at: $CONFIG_FILE"
    exit 1
fi

echo -e "${CYAN}======================================${NC}"
echo -e "${CYAN}   Claude Code Configuration Editor   ${NC}"
echo -e "${CYAN}======================================${NC}"

# Prompt for user input with corrected color strings
# Using printf to ensure colors render correctly across different shells
printf "${YELLOW}Enter New ANTHROPIC_AUTH_TOKEN: ${NC}"
read -r NEW_TOKEN

printf "${YELLOW}Enter New ANTHROPIC_BASE_URL: ${NC}"
read -r NEW_URL

# Validate input
if [[ -z "$NEW_TOKEN" || -z "$NEW_URL" ]]; then
    log_error "Both Token and Base URL are required. Operation aborted."
    exit 1
fi

# Create backup
log_info "Creating backup at $BACKUP_FILE..."
cp "$CONFIG_FILE" "$BACKUP_FILE"

# Prepare updated JSON using a temporary file
TMP_FILE=$(mktemp)
jq --arg token "$NEW_TOKEN" \
   --arg url "$NEW_URL" \
   '.env.ANTHROPIC_AUTH_TOKEN = $token | .env.ANTHROPIC_BASE_URL = $url' \
   "$CONFIG_FILE" > "$TMP_FILE"

if [ $? -eq 0 ]; then
    mv "$TMP_FILE" "$CONFIG_FILE"
    log_success "Settings updated successfully!"

    echo -e "\n${BLUE}Updated Configuration Summary:${NC}"
    echo -e "${CYAN}--------------------------------------${NC}"
    # Masking the token for security in output
    jq -j -r '.env | "Token: " + (.ANTHROPIC_AUTH_TOKEN[:4] + "****") + "\nURL:   " + .ANTHROPIC_BASE_URL + "\n"' "$CONFIG_FILE"
    echo -e "${CYAN}--------------------------------------${NC}"
else
    log_error "Failed to process JSON. Rolling back..."
    rm -f "$TMP_FILE"
    exit 1
fi