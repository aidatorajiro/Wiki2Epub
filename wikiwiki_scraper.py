# wikiwiki.jp scraper

from maker import EpubMaker
import os
import sys
from webutil import *
from bs4 import BeautifulSoup
import datetime
import re
from urllib.parse import urlparse, parse_qs, urljoin
import base64
import hashlib
import time


class WikiwikiScraper:
    
    def __init__(self, wiki_id, book_id=None):
        self.fileurls = []
        self.files = {}
        self.pageurls = []
        self.pages = {}
        self.book_title = None
        self.path_to_cassette = None
        
        self.wiki_id = wiki_id
        self.hostname = "wikiwiki.jp"
        self.rooturl = "http://" + self.hostname + "/"
        if book_id == None:
            self.book_id = wiki_id + datetime.datetime.now().strftime("_%Y%m%d%H%M%S") # 現在時刻から書籍のIDを作成
        else:
            self.book_id = book_id
        self.base_url = self.rooturl + wiki_id + "/" # サイトのトップのURLを取得
    
    # wiki_idからそのwikiに含まれる全てのページのURLを取得する
    def get_all_urls(self, wiki_id):
        base_url = self.rooturl + self.wiki_id + "/"
        sitemap = BeautifulSoup(get_global_file(base_url + "?cmd=list"))
        site_urls = list(map(lambda x: x.get("href"), sitemap.select("#body > ul > li > ul > li > a")))
        return site_urls
    
    # インターネット上のデータをダウンロードする
    def download(self, url, path):
        url = urljoin(self.base_url, url)
        if not path in self.files:
            obj = get_global_file_as_object(url)
            self.files[path] = (obj.content, obj.headers.get("Content-Type").split(";")[0])
    
    # 各要素ごとに処理をする。
    # 処理その１：scriptタグだったりしたら要素自体を消す、などの検閲作業
    # 処理その２：cssやimgのURLをepub内のものに置き換える(sha256する)
    # 処理その３：画像ファイルやcssなどをダウンロード＆self.filesに登録
    #
    # 作業メモ:
    # 先ずは、hrefやsrcを全てsha256して内部のアドレスに置き換える。
    # 次に、アドレスのうち画像やcssなどのアセットを指しているだろうと思われるものを全て取得し、filesに登録する。（その際パスはアドレスをsha256したもの+拡張子にする）
    def process_element(self, element):
        
        if element.name == "script": # scriptタグは問答無用で削除
            element.extract()
            return
        
        # href属性関連
        href = element.get("href")
        
        if href:
            o = urlparse(href)
            qs = parse_qs(o[4])
            
            if not href.startswith("#"):
                if re.match(r".+?/\?[^=\?]+$", href): # if page
                    path = hashlib.sha256(href.encode()).hexdigest() + ".xhtml"
                elif re.match(r".+?\.css(\?.+)?$", href): # if css
                    path = "../files/" + hashlib.sha256(href.encode()).hexdigest() + ".css"
                    self.download(href, hashlib.sha256(href.encode()).hexdigest() + ".css")
                else:
                    path = ""
                    print("dropped url: " + href)
                
                element["href"] = path
        
        # src属性関連
        src = element.get("src")
        
        if src:
            o = urlparse(src)
            qs = parse_qs(o[4])
            
            image_re = re.match(r".+?\.(jpg|jpeg|gif|png)(\?.+)?$", src)
            if image_re: # if image
                path = "../files/" + hashlib.sha256(src.encode()).hexdigest() + "." + image_re.group(1)
                self.download(src, hashlib.sha256(src.encode()).hexdigest() + "." + image_re.group(1))
            else:
                path = ""
                print("dropped url: " + src)
            
            element["src"] = path
    
    # wiki_idから個別にepubを生成する。
    def make(self, path_to_epub, path_to_cassette):
        self.path_to_cassette = path_to_cassette
        with vcr.use_cassette(self.path_to_cassette, record_mode="new_episodes", match_on=['uri']):
            print("getting site info...")
            top_page = BeautifulSoup(get_global_file(self.base_url)) # トップページを取得
            self.book_title = top_page.title.text # タイトルを取得
            
            print("getting site map...")
            self.pageurls = self.get_all_urls(self.wiki_id) # サイトの全ページのURLを取得
            
            print("generating pages...")
            
            for i, pageurl in enumerate(self.pageurls):
                print("Page: " + pageurl + " " + str(i) + "/" + str(len(self.pageurls)))
                
                page = BeautifulSoup(get_global_file(pageurl))
                
                list(map(self.process_element, page.select("*")))
                
                self.pages[hashlib.sha256(pageurl.encode()).hexdigest()] = (page.title.text, {"head": str(page.head), "body": str(page.body)})
            
            print("constructing an EpubMaker object...")
            maker = EpubMaker("ja-JP", self.book_title, "知らん", "知らん", "知らん", identifier=self.book_id)
            
            print("adding files and pages to the EpubMaker object...")
            for name, page in self.pages.items():
                maker.addPage(name, page[0], page[1])
            
            for filename, file in self.files.items():
                maker.addFile(filename, file[0], file[1])
            
            maker.addFile("style.css", get_local_file(script_path("assets", "style.css")), "text/css")
            
            print("making epub file...")
            maker.doMake(path)

if __name__ == '__main__':
    scraper = WikiwikiScraper(sys.argv[1])
    scraper.make(script_path("out", scraper.book_id + ".epub"), script_path("out", scraper.book_id + ".cassette"))