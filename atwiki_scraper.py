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
import vcr.matchers
import extensions
from wikiwiki_scraper import WikiwikiScraper


class AtwikiScraper(WikiwikiScraper):
    
    def __init__(self, server_id, wiki_id, book_id=None):
        
        WikiwikiScraper.__init__(self, wiki_id, book_id)
        
        self.hostname = "www%d.atwiki.jp" % server_id
        self.rooturl = "http://" + self.hostname + "/"
        if book_id == None:
            self.book_id = wiki_id + datetime.datetime.now().strftime("_%Y%m%d%H%M%S") # 現在時刻から書籍のIDを作成
        else:
            self.book_id = book_id
        self.base_url = self.rooturl + wiki_id + "/" # サイトのトップのURLを取得
    
    # wikiに含まれる全てのページのURLを取得する
    def get_all_urls(self):
        soup = BeautifulSoup(get_global_file(self.base_url + "list"), "lxml")
        number_of_sitemaps = len(soup.select("div.pagelist > p")[2].select("span") + soup.select(".pagelist > p")[2].select("a"))
        site_urls = []
        for i in range(0, number_of_sitemaps):
            soup = BeautifulSoup(get_global_file(self.base_url + "list?sort=create&pp=%d" % i), "lxml")
            site_urls += list(map(lambda x: x.get("href"), soup.select("table.pagelist > tr > td > a")))
        return site_urls
    
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
        
        if element.get("onclick"):
            del element["onclick"] # onclickは問答無用で削除
        
        if element.get("style"):
            element["style"] = re.sub(r"display\s*:\s*none", "", element.get("style")) # display:noneがありすぎるとkindlegenでエラーが出るので・・・・
        
        # href属性関連
        href = element.get("href")
        
        if href:
            o = urlparse(href)
            qs = parse_qs(o[4])
            
            if not href.startswith("#"):
                re_1 = re.match(r"(.+?/pages/\d+.html)(#.*)$", href)
                if re_1: # if page with anchor
                    path = hashlib.sha256(re_1.group(1).encode()).hexdigest() + ".xhtml" + re_1.group(2)
                elif re.match(r".+?/pages/\d+.html$", href) or href == "/" + self.wiki_id + "/": # if page with no anchor or toppage
                    path = hashlib.sha256(href.encode()).hexdigest() + ".xhtml"
                elif re.match(r".+?\.css(\?.+)?$", href): # if css
                    try:
                        path = "../files/" + hashlib.sha256(href.encode()).hexdigest() + ".css"
                        self.download(href, hashlib.sha256(href.encode()).hexdigest() + ".css", "custom", "text/css")
                    except Exception as e:
                        path = ""
                        print("network error occurred: " + str(e))
                else:
                    path = ""
                    print("dropped url: " + href)
                
                element["href"] = path
        
        # src属性関連
        src = element.get("src")
        
        if src:
            o = urlparse(src)
            qs = parse_qs(o[4])
            
            image_re_1 = re.match(r".+?\.(jpg|jpeg|gif|png)(\?.+)?$", src)
            image_re_2 = re.match(r"^//cdn\d+\.atwikiimg\.com/.+?$", src)
            if image_re_1: # if image
                try:
                    path = "../files/" + hashlib.sha256(src.encode()).hexdigest()
                    self.download(src, hashlib.sha256(src.encode()).hexdigest(), "python-magic")
                except Exception as e:
                    path = ""
                    print("network error occurred: " + str(e))
            elif image_re_2: # if image with no extension
                try:
                    path = "../files/" + hashlib.sha256(src.encode()).hexdigest()
                    self.download(src, hashlib.sha256(src.encode()).hexdigest(), "python-magic")
                except Exception as e:
                    path = ""
                    print("network error occurred: " + str(e))
            else:
                path = ""
                print("dropped url: " + src)
            
            element["src"] = path
    
    # 個別にepubを生成する。
    def make(self, path_to_epub, path_to_cassette, record_mode="new_episodes", match_on=['uri']):        
        self.path_to_cassette = path_to_cassette
        
        with vcr.use_cassette(self.path_to_cassette, record_mode=record_mode, match_on=match_on) as cassette:
            # サーバに負荷をかけすぎないようにオンラインから取ってくるときは少し眠らせる黒魔術
            def sleep(x):
                for i in cassette.requests:
                    if vcr.matchers.requests_match(x, i, cassette._match_on):
                        return x
                time.sleep(1)
                return x
            cassette._before_record_request = sleep
            
            print("getting site info...")
            top_page = BeautifulSoup(get_global_file(self.base_url), "lxml") # トップページを取得
            self.book_title = top_page.select('head > meta[property="og:site_name"]')[0].get("content") # タイトルを取得
            
            print("getting site map...")
            self.pageurls = self.get_all_urls() # サイトの全ページのURLを取得
            
            print("generating pages...")
            
            for i, pageurl in enumerate(self.pageurls):
                print("Page: " + pageurl + " " + str(i) + "/" + str(len(self.pageurls)))
                
                page = BeautifulSoup(get_global_file(pageurl), "lxml")
                
                list(map(self.process_element, page.select("*")))
                
                page.head.append(page.new_tag('link', rel="stylesheet", href="../files/style.css", type="text/css"))
                
                self.pages[hashlib.sha256(pageurl.encode()).hexdigest()] = (page.title.text, {"head": str(page.head), "body": str(page.body)})
            
            print("constructing an EpubMaker object...")
            maker = EpubMaker("ja-JP", self.book_title, "知らん", "知らん", "知らん", identifier=self.book_id)
            
            print("adding files and pages to the EpubMaker object...")
            for name, page in self.pages.items():
                maker.addPage(name, page[0], page[1])
            
            for filename, file in self.files.items():
                maker.addFile(filename, file[0], file[1])
            
            maker.addFile("style.css", get_local_file(script_path("assets", "atwiki", "style.css")), "text/css")
            
            print("making epub file...")
            maker.doMake(path_to_epub)

if __name__ == '__main__':
    scraper = AtwikiScraper(int(sys.argv[1]), sys.argv[2])
    scraper.make(sys.argv[3], sys.argv[4])