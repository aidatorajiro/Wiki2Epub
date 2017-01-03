# atwiki.jp scraper

import sys
from webutil import *
from atwiki_scraper import AtwikiScraper

if __name__ == '__main__':
    scraper = AtwikiScraper(int(sys.argv[1]), sys.argv[2])
    scraper.page_only = True
    scraper.make(sys.argv[3], sys.argv[4], record_mode="none")