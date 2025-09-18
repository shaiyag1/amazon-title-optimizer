#!/bin/bash
# Unix/Linux/Mac shell script for title optimization
# Usage: ./optimize_title.sh "original title" "search_term1" ["search_term2"] ["search_term3"]

if [ $# -lt 2 ]; then
    echo "Usage: $0 \"original title\" \"search_term1\" [\"search_term2\"] [\"search_term3\"]"
    echo ""
    echo "Examples:"
    echo "  $0 \"LED Light Bulb 60W\" \"outdoor lighting\""
    echo "  $0 \"Purity Eyeglass Cleaner Kit\" \"refill\" \"spray\" \"lens cleaner\""
    exit 1
fi

python3 optimize_title_cli.py "$@"
