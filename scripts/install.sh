#!/bin/sh

set -e

echo "Downloading build_it for $(uname -s)..."
sudo curl -L "https://github.com/Dasero197/build_it/releases/latest/download/build_it-$(uname -s | tr '[:upper:]' '[:lower:]')" -o /usr/local/bin/build_it
sudo chmod +x /usr/local/bin/build_it

echo ""
echo "✅ build_it installed successfully to /usr/local/bin/build_it!"
echo "Run 'build_it info' to get started."
