import csv
import os
import tempfile
import zipfile
import genshi
import datetime
import uuid
import shutil
from genshi.template import TemplateLoader
from genshi.template.text import NewTextTemplate

def toShortLangcode(long_code):
	with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'languages.csv'), 'r') as f:
		reader = csv.reader(f)
		header = next(reader) # ヘッダは無視
		for row in reader:
			if row[6] == long_code:
				return row[4]
	return None

class EpubMaker:
	# コンストラクタ
	# (言語コード(ja-JPなど), 本のタイトル, 作者, 権利, 発行者, UUID, content.opfのテンプレート)
	def __init__(self, language, title, author, rights, publisher, identifier=uuid.uuid4(), toc_template="toc.xhtml", toc_data=None, opf_template="content.opf", opf_data=None):
		# 表側
		
		self.language_long = language
		
		self.language_short = toShortLangcode(language)
		if not self.language_short:
			raise(Exception("Language Culture Code not exists"));
		
		self.title = title
		
		self.author = author
		
		self.rights = rights
		
		self.publisher = publisher
		
		self.identifier = identifier
		
		self.opf = {"template": opf_template, "data": opf_data}
		
		self.toc = {"template": toc_template, "data": toc_data}
		
		# 裏側
		
		self.date = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
		
		self.depth = 1
		
		self.pages = {}
		
		self.files = {}
		
		self.default_stylesheet_file = None
		
		self.cover_image = None
	
	# genshiのxhtml templateからページを作る
	def addPage(self, name, title, data, template="page.xhtml"):
		self.pages[name] = {"title": title, "data": data, "template": template}
	
	# 生データ（バイナリ）を渡してファイルを作る
	def addFile(self, filename, data, type):
		if filename in self.files:
			raise(Exception("Filename already exists"));
		
		self.files[filename] = {"data": data, "type": type, "id": uuid.uuid4()}
	
	# genshiのtext templateからファイルを作る
	def addFileFromTemplate(self, filename, data, type, template):
		if filename in self.files:
			raise(Exception("Filename already exists"));
		
		self.files[filename] = {"data": data, "type": type, "id": uuid.uuid4(), "template": template}
	
	# デフォルトのスタイルシートファイルを決める
	def setDefaultStylesheetFile(self, filename):
		if filename not in self.files:
			raise(Exception("Filename not exists"));
		
		self.default_stylesheet_file = filename
	
	# カバー画像ファイルを決める
	def setCoverImage(self, filename):
		if filename not in self.files:
			raise(Exception("Filename not exists"));
		
		self.cover_image = filename
	
	#EPUBの構造
	#EPUB
	#├── minetype
	#│
	#├── META-INF
	#│   └── container.xml
	#│
	#├── EPUB
	#│   ├── toc.xhtml
	#│   ├── content.opf
	#│   ├── files
	#│   │   ├── stylesheet.css
	#│   │   └── image.jpg
	#│   ├── pages
	#│   │   ├── aaaa.xhtml
	#│   │   ├── bbbb.xhtml
	#│   │   ├──     .
	#│   │   ├──     .
	#│   │   ├──     .
	
	def doMake(self, path):
		loader = TemplateLoader([os.path.join(os.path.dirname(os.path.realpath(__file__)), "template")])
		
		rootdir = tempfile.mkdtemp()
		print(rootdir)
		
		try:
			#File minetype
			with open(os.path.join(rootdir, 'mimetype'), 'w') as f:
				f.write('application/epub+zip')
			
			#Directory META-INF/ (container.xml)
			os.mkdir(os.path.join(rootdir, 'META-INF'))
			
			with open(os.path.join(rootdir, 'META-INF/container.xml'), 'w') as f:
				f.write(loader.load('container.xml').generate(**self.__dict__).render('xml'))
			
			#Directory OEBPS/ (toc.ncx, content.opf, and xhtml documents)
			os.mkdir(os.path.join(rootdir, 'EPUB'))
			
			with open(os.path.join(rootdir, 'EPUB/content.opf'), 'w') as f:
				tmp = self.__dict__.copy()
				tmp.update(self.opf)
				tmp["path"] = 'EPUB/content.opf'
				f.write(loader.load(self.opf["template"]).generate(**tmp).render('xml'))
			
			with open(os.path.join(rootdir, 'EPUB/toc.xhtml'), 'w') as f:
				tmp = self.__dict__.copy()
				tmp.update(self.toc)
				tmp["path"] = 'EPUB/toc.xhtml'
				f.write(loader.load(self.toc["template"]).generate(**tmp).render('xhtml'))
			
			os.mkdir(os.path.join(rootdir, 'EPUB/pages'))
			
			for filename, page in self.pages.items():
				with open(os.path.join(rootdir, 'EPUB/pages/%s.xhtml' % filename), 'w') as f:
					tmp = self.__dict__.copy()
					tmp.update(page)
					tmp["path"] = 'EPUB/pages/%s.xhtml' % filename
					f.write(loader.load(page["template"]).generate(**tmp).render('xhtml'))
			
			os.mkdir(os.path.join(rootdir, 'EPUB/files'))
			
			for filename, file in self.files.items():
				if "template" in file:
					with open(os.path.join(rootdir, 'EPUB/files/%s' % filename), 'w') as f:
						tmp = self.__dict__.copy()
						tmp.update(file)
						tmp["path"] = 'EPUB/files/%s' % filename
						f.write(loader.load(file["template"], cls=NewTextTemplate).generate(**tmp).render('text'))
				else:
					with open(os.path.join(rootdir, 'EPUB/files/%s' % filename), 'wb') as f:
						f.write(file["data"])
			
			with zipfile.ZipFile(path, 'w') as zipf:
				os.chdir(rootdir)
				for root, dirs, files in os.walk(rootdir):
					for file in files:
						zipf.write(os.path.relpath(os.path.join(root, file), rootdir))
			
		except Exception as e:
			raise e
		finally:
			shutil.rmtree(rootdir)