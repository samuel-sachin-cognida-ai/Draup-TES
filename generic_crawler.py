#!/usr/bin/env python3
"""
generic_crawler.py — entry point for the Healthcare AI crawler.

Usage:
    python generic_crawler.py                         # crawl all vendors
    python generic_crawler.py --vendor aws_bedrock    # single vendor
    python generic_crawler.py --vendor openai --vendor anthropic
    python generic_crawler.py --group cloud_platform  # one group
    python generic_crawler.py --list                  # list configured vendors
"""
from crawler.runner import main

if __name__ == "__main__":
    main()
