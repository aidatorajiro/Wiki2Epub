# Wiki2Epub

AtwikiやWikiwikiのようなレンタルWikiサービス内の文章や画像を、Epubに変換するプログラム。

Atwiki:
https://atwiki.jp/

Wikiwiki:
http://wikiwiki.jp/

## Usage

On console:

$ mkdir out

$ python ./wikiwiki-scraper.py sample

これで、http://wikiwiki.jp/sample/内の文章がepubとなってout/内に出来上がります。

On python:

from wikiwiki_scraper import WikiwikiScraper

scraper = WikiwikiScraper("sample")

scraper.make("/path/to/epub/file.epub", "/path/to/cassette/file.cassette")