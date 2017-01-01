# wikiwiki.jp scraper

import sys
from webutil import *
from wikiwiki_scraper import WikiwikiScraper

if __name__ == '__main__':
    scraper = WikiwikiScraper(sys.argv[1])
    scraper.make(sys.argv[2], sys.argv[3], record_mode="none")