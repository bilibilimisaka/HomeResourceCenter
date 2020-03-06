#!/usr/bin/env python3
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import os
import base64

import time
import aiopg
import bcrypt
import markdown
import os.path
import psycopg2
import re
import requests
import unicodedata
import numpy as np

import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.locks
import tornado.options
import tornado.web

from tornado.options import define, options
from tornado.process import subprocess
from tornado import gen

from io import BytesIO
from PIL import Image

from bert_serving.client import BertClient
from ke.ke4web import ke4web
from ke.evalKE import evalKE
from yolov3ocr import ocr
from cvTM.cvMatchTemplate import MatchTemplate
from cvTM.cvPicMatch import picMatchTemplate
from urllib import parse
from gDetect import detect
from uiDetect import ui_detect
from gTextDetect.model import detect as gtextdetect

define("port", default=8888, help="run on the given port", type=int)
define("db_host", default="127.0.0.1", help="sservice database host")
define("db_port", default=5432, help="sservice database port")
define("db_database", default="sservice", help="sservice database name")
define("db_user", default="sservice", help="sservice database user")
define("db_password", default="sservice", help="sservice database password")

class NoResultError(Exception):
    pass


async def maybe_create_tables(db):
    try:
        with (await db.cursor()) as cur:
            await cur.execute("SELECT COUNT(*) FROM entries LIMIT 1")
            await cur.fetchone()
    except psycopg2.ProgrammingError:
        with open("schema.sql") as f:
            schema = f.read()
        with (await db.cursor()) as cur:
            await cur.execute(schema)


class Application(tornado.web.Application):
    def __init__(self, db):
        self.db = db
        handlers = [
            (r"/", HomeHandler),
            (r"/archive", ArchiveHandler),
            (r"/feed", FeedHandler),
            (r"/entry/([^/]+)", EntryHandler),
            (r"/compose", ComposeHandler),
            (r"/auth/create", AuthCreateHandler),
            (r"/auth/login", AuthLoginHandler),
            (r"/auth/logout", AuthLogoutHandler),
            (r"/index.html", DashBoardHandler),
            (r"/buttons.html", ButtonsHandler),
            (r"/cards.html", CardsHandler),
            (r"/login.html", LoginHandler),
            (r"/register.html", RegisterHandler),
            (r"/forgot-password.html", ForgotPasswordHandler),
            (r"/404.html", ErrorHandler),
            (r"/similarity.html", BlankPageHandler),
            (r"/summary.html", SummaryPageHandler),
            (r"/charts.html", ChartsHandler),
            (r"/tables.html", TablesHandler),
            (r"/utilities-animation.html", AnimationHandler),
            (r"/utilities-border.html", BorderHandler),
            (r"/utilities-color.html", ColorHandler),
            (r"/utilities-other.html", OtherHandler),
            (r"/ocr-api", OcrApiHandler),
            (r"/python-api", PythonApiHandler),
            (r"/similarity-api", SimilarityApiHandler),
            (r"/sim-api", SimUrlencodeApiHandler),
            (r"/picSim-api", PicSimApiHandler),
            (r"/picMatch-api", TemplateMatchApiHandler),
            (r"/gDetect-api", GDetectApiHandler),
            (r"/uiDetect-api", UIDetectApiHandler),
            (r"/gTextDetect", GTextDetectApiHandler),
            (r"/entry.html/([^/]+)", EntryPageHandler),
        ]
        settings = dict(
            blog_title=u"ServiceSimilarity",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            ui_modules={"Entry": EntryModule, "Table": TableModule},
            xsrf_cookies=False,
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            login_url="/login.html",
            debug=True,
        )
        eval_instant = evalKE()
        gtext_instant = gtextdetect()
        self.model = eval_instant.my_word2vec()
        self.gModel = detect.preload()
        self.uiModel = ui_detect.preload()
        self.gTextModel = gtext_instant.preload()
        super(Application, self).__init__(handlers, **settings)
        


class BaseHandler(tornado.web.RequestHandler):
    def row_to_obj(self, row, cur):
        """Convert a SQL row to an object supporting dict and attribute access."""
        obj = tornado.util.ObjectDict()
        for val, desc in zip(row, cur.description):
            obj[desc.name] = val
        return obj

    async def execute(self, stmt, *args):
        """Execute a SQL statement.

        Must be called with ``await self.execute(...)``
        """
        with (await self.application.db.cursor()) as cur:
            await cur.execute(stmt, args)

    async def query(self, stmt, *args):
        """Query for a list of results.

        Typical usage::

            results = await self.query(...)

        Or::

            for row in await self.query(...)
        """
        with (await self.application.db.cursor()) as cur:
            await cur.execute(stmt, args)
            return [self.row_to_obj(row, cur) for row in await cur.fetchall()]

    async def queryuser(self, stmt, *args):
        """Query for a list of results.

        Typical usage::

            results = await self.query(...)

        Or::

            for row in await self.query(...)
        """
        with (await self.application.db.cursor()) as cur:
            await cur.execute(stmt, args)
            return [row[0] for row in await cur.fetchall()]

    async def queryone(self, stmt, *args):
        """Query for exactly one result.

        Raises NoResultError if there are no results, or ValueError if
        there are more than one.
        """
        results = await self.query(stmt, *args)
        if len(results) == 0:
            raise NoResultError()
        elif len(results) > 1:
            raise ValueError("Expected 1 result, got %d" % len(results))
        return results[0]

    async def prepare(self):
        # get_current_user cannot be a coroutine, so set
        # self.current_user in prepare instead.
        user_id = self.get_secure_cookie("blogdemo_user")
        if user_id:
            self.current_user = await self.queryone(
                "SELECT * FROM authors WHERE id = %s", int(user_id)
            )

    async def any_author_exists(self):
        return bool(await self.query("SELECT * FROM authors LIMIT 1"))

    async def register_author_exists(self, email):
        return bool(await self.query("SELECT * FROM authors WHERE email='{}'".format(email)))
    async def ocrInstant(self, pic):
        ocrAi = ocr.OCR()
        return ocrAi.general_ocr(pic)


class HomeHandler(BaseHandler):
    async def get(self):
        entries = await self.query(
            "SELECT * FROM entries ORDER BY published DESC LIMIT 5"
        )
        if not entries:
            self.redirect("/compose")
            return
        self.render("home.html", entries=entries)


class EntryHandler(BaseHandler):
    async def get(self, slug):
        entry = await self.queryone("SELECT * FROM entries WHERE slug = %s", slug)
        if not entry:
            raise tornado.web.HTTPError(404)
        self.render("entry.html", entry=entry)


class ArchiveHandler(BaseHandler):
    async def get(self):
        entries = await self.query("SELECT * FROM entries ORDER BY published DESC")
        self.render("archive.html", entries=entries)


class FeedHandler(BaseHandler):
    async def get(self):
        entries = await self.query(
            "SELECT * FROM entries ORDER BY published DESC LIMIT 10"
        )
        self.set_header("Content-Type", "application/atom+xml")
        self.render("feed.xml", entries=entries)


class ComposeHandler(BaseHandler):
    @tornado.web.authenticated
    async def get(self):
        id = self.get_argument("id", None)
        entry = None
        if id:
            entry = await self.queryone("SELECT * FROM entries WHERE id = %s", int(id))
        self.render("compose.html", entry=entry)

    @tornado.web.authenticated
    async def post(self):
        id = self.get_argument("id", None)
        title = self.get_argument("title")
        text = self.get_argument("markdown")
        html = markdown.markdown(text)
        if id:
            try:
                entry = await self.queryone(
                    "SELECT * FROM entries WHERE id = %s", int(id)
                )
            except NoResultError:
                raise tornado.web.HTTPError(404)
            slug = entry.slug
            await self.execute(
                "UPDATE entries SET title = %s, markdown = %s, html = %s "
                "WHERE id = %s",
                title,
                text,
                html,
                int(id),
            )
        else:
            slug = unicodedata.normalize("NFKD", title)
            slug = re.sub(r"[^\w]+", " ", slug)
            slug = "-".join(slug.lower().strip().split())
            slug = slug.encode("ascii", "ignore").decode("ascii")
            if not slug:
                slug = "entry"
            while True:
                e = await self.query("SELECT * FROM entries WHERE slug = %s", slug)
                if not e:
                    break
                slug += "-2"
            await self.execute(
                "INSERT INTO entries (author_id,title,slug,markdown,html,published,updated)"
                "VALUES (%s,%s,%s,%s,%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
                self.current_user.id,
                title,
                slug,
                text,
                html,
            )
            
        self.redirect("/entry/" + slug)


class AuthCreateHandler(BaseHandler):
    def get(self):
        self.render("create_author.html")

    async def post(self):
        if await self.any_author_exists():
            raise tornado.web.HTTPError(400, "author already created")
        hashed_password = await tornado.ioloop.IOLoop.current().run_in_executor(
            None,
            bcrypt.hashpw,
            tornado.escape.utf8(self.get_argument("password")),
            bcrypt.gensalt(),
        )
        author = await self.queryone(
            "INSERT INTO authors (email, name, hashed_password) "
            "VALUES (%s, %s, %s) RETURNING id",
            self.get_argument("email"),
            self.get_argument("name"),
            tornado.escape.to_unicode(hashed_password),
        )
        self.set_secure_cookie("blogdemo_user", str(author.id))
        self.redirect(self.get_argument("next", "/"))


class AuthLoginHandler(BaseHandler):
    async def get(self):
        # If there are no authors, redirect to the account creation page.
        if not await self.any_author_exists():
            self.redirect("/auth/create")
        else:
            self.render("login.html", error=None)

    async def post(self):
        try:
            author = await self.queryone(
                "SELECT * FROM authors WHERE email = %s", self.get_argument("email")
            )
        except NoResultError:
            self.render("login.html", error="email not found")
            return
        hashed_password = await tornado.ioloop.IOLoop.current().run_in_executor(
            None,
            bcrypt.hashpw,
            tornado.escape.utf8(self.get_argument("password")),
            tornado.escape.utf8(author.hashed_password),
        )
        hashed_password = tornado.escape.to_unicode(hashed_password)
        if hashed_password == author.hashed_password:
            self.set_secure_cookie("blogdemo_user", str(author.id))
            self.redirect(self.get_argument("next", "/"))
        else:
            self.render("login.html", error="incorrect password")


class AuthLogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("blogdemo_user")
        self.redirect(self.get_argument("next", "/"))

class EntryModule(tornado.web.UIModule):
    def render(self, entry):
        return self.render_string("modules/entry.html", entry=entry)

class TableModule(tornado.web.UIModule):
    def render(self, entry):
        return self.render_string("modules/table.html", entry=entry)

## website

class DashBoardHandler(BaseHandler):
    """docstring for DashBoardHandler"""
    async def get(self):
        if not await self.any_author_exists():
            self.redirect("register.html")
        elif not self.current_user:
            self.redirect("login.html")
        entries = await self.query("SELECT * FROM entries ORDER BY published DESC")
        self.render("index.html", entries=entries, nickname=self.current_user.nick_name)

class ButtonsHandler(BaseHandler):
    """docstring for ButtonsHandler"""
    def get(self):
        self.render("components/buttons.html")
        
class CardsHandler(BaseHandler):
    """docstring for CardsHandler"""
    def get(self):
        self.render("components/cards.html")

class LoginHandler(BaseHandler):
    """docstring for ErrorHandler"""
    async def get(self):
        # If there are no authors, redirect to the account creation page.
        if not await self.any_author_exists():
            self.redirect("register.html")
        else:
            self.render("pages/login.html", error=None)

    async def post(self):
        try:
            author = await self.queryone(
                "SELECT * FROM authors WHERE email = %s", self.get_argument("email")
            )
        except NoResultError:
            self.render("login.html", error="email not found")
            return
        hashed_password = await tornado.ioloop.IOLoop.current().run_in_executor(
            None,
            bcrypt.hashpw,
            tornado.escape.utf8(self.get_argument("password")),
            tornado.escape.utf8(author.hashed_password),
        )
        hashed_password = tornado.escape.to_unicode(hashed_password)
        if hashed_password == author.hashed_password:
            data = {
                "email":self.get_argument("email"),
                "password":hashed_password,
                "success":True,
            }
            self.write(data)
            self.set_secure_cookie("blogdemo_user", str(author.id))
            # self.redirect(self.get_argument("next", "/"))
        else:
            # self.render("pages/login.html", error="incorrect password")
            data = {
                "success":False,
            }
            self.write(data)

class RegisterHandler(BaseHandler):
    """docstring for ErrorHandler"""
    def get(self):
        self.render("pages/register.html")

    async def post(self):
        email = self.get_argument("email")
        if await self.register_author_exists(email):
            raise tornado.web.HTTPError(400, "author already created")
        hashed_password = await tornado.ioloop.IOLoop.current().run_in_executor(
            None,
            bcrypt.hashpw,
            tornado.escape.utf8(self.get_argument("password")),
            bcrypt.gensalt(),
        )
        author = await self.queryone(
            "INSERT INTO authors (email, real_name, nick_name, hashed_password) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            email,
            self.get_argument("realname"),
            self.get_argument("nickname"),
            tornado.escape.to_unicode(hashed_password),
        )
        self.set_secure_cookie("blogdemo_user", str(author.id))
        self.redirect(self.get_argument("next", "/"))

class ForgotPasswordHandler(BaseHandler):
    """docstring for ErrorHandler"""
    def get(self):
        self.render("pages/forgot-password.html")

class ErrorHandler(BaseHandler):
    """docstring for ErrorHandler"""
    def get(self):
        self.render("pages/404.html")

class BlankPageHandler(BaseHandler):
    """docstring for ErrorHandler"""
    @tornado.web.authenticated
    async def get(self):
        id = self.get_argument("id", None)
        entry = None
        if id:
            entry = await self.queryone("SELECT * FROM entries WHERE id = %s", int(id))
        self.render("pages/similarity.html", entry=entry, nickname=self.current_user.nick_name)

    # @gen.coroutine
    # def run_command(cmd):
    #     """
    #     """
    #     process = Subprocess([cmd], 
    #         stdout=Subprocess.STREAM, 
    #         stderr=Subprocess.STREAM, 
    #         shell=True)

    #     out, err = yield [process.stdout.read_until_close(), process.stderr.read_until_close()]
    #     raise gen.Return((out, err))

    # def subprocess(self, cmd, callback):
    #     ioloop = tornado.ioloop.IOLoop.instance()
    #     PIPE = subprocess.PIPE
    #     pipe = subprocess.Popen(cmd , shell=True, stdin=PIPE, stdout=PIPE,
    #                         stderr=subprocess.STDOUT, close_fds=True)
    #     fd = pipe.stdout.fileno()
        
    #     def recv(*args):
    #         data = pipe.stdout.readline()
    #         if data:  self.send(data)
    #         elif pipe.poll() is not None:
    #             ioloop.remove_handler(fd)
    #             self.send(None)
        
    #     # read handler
    #     ioloop.add_handler(fd, recv, ioloop.READ)



    @tornado.web.authenticated
    async def post(self):
        id = self.get_argument("id", None)
        title = self.get_argument("title")
        text = self.get_argument("markdown")
        html = markdown.markdown(text)
        if id:
            try:
                entry = await self.queryone(
                    "SELECT * FROM entries WHERE id = %s", int(id)
                )
            except NoResultError:
                raise tornado.web.HTTPError(404)
            slug = entry.slug
            await self.execute(
                "UPDATE entries SET title = %s, markdown = %s, html = %s "
                "WHERE id = %s",
                title,
                text,
                html,
                int(id),
            )
        else:
            next_id = await self.queryone("SELECT * FROM entries_id_seq")
            slug = unicodedata.normalize("NFKD", title)
            slug = re.sub(r"[^\w]+", " ", slug)
            slug = "-".join(slug.lower().strip().split())
            slug = slug.encode("ascii", "ignore").decode("ascii")
            if not slug:
                slug = "entry"
            while True:
                e = await self.query("SELECT * FROM entries WHERE slug = %s", slug)
                if not e:
                    break
                slug = "entry-" + str(int(next_id.last_value)+1)
            try:
                cmd = "sh ~/Downloads/work/run_similarity.sh {} {}".format(title, self.current_user.nick_name)
                # os.system(cmd)
                subprocess.run(cmd, shell=True)
            except Exception as e:
                raise tornado.web.HTTPError(400, "python down")
            else:
                pass
            
            with open("/Users/apple/Downloads/work/final_result_"+self.current_user.nick_name, "r", encoding="utf8") as fr:
                for i, line in enumerate(fr.readlines()):
                    text += line
                    html += markdown.markdown(line)

            await self.execute(
                "INSERT INTO entries (author_id,title,slug,markdown,html,published,updated)"
                "VALUES (%s,%s,%s,%s,%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
                self.current_user.id,
                title,
                slug,
                text,
                html,
            )
            
        self.redirect("/entry.html/" + slug)

class SummaryPageHandler(BaseHandler):
    async def get(self):
        entries = await self.query(
            "SELECT * FROM entries ORDER BY published DESC"
        )
        if not entries:
            self.redirect("/404.html")
            return
        self.render("pages/summary.html", entries=entries, nickname=self.current_user.nick_name)


class ChartsHandler(BaseHandler):
    """docstring for ChartsHandler"""
    def get(self):
        self.render("charts.html")

class TablesHandler(BaseHandler):
    """docstring for tablesHandler"""
    async def get(self):
        entries = await self.query(
            "SELECT * FROM entries"
        )
        if not entries:
            self.redirect("/404.html")
            return
        self.render("tables.html", entries=entries, nickname=self.current_user.nick_name)

class AnimationHandler(BaseHandler):
    """docstring for AnimationHandler"""
    def get(self):
        self.render("utilities/utilities-animation.html")

class BorderHandler(BaseHandler):
    """docstring for BorderHandler"""
    def get(self):
        self.render("utilities/utilities-border.html")

class ColorHandler(BaseHandler):
    """docstring for ColorHandler"""
    def get(self):
        self.render("utilities/utilities-color.html")

class OtherHandler(BaseHandler):
    """docstring for OtherHandler"""
    def get(self):
        self.render("utilities/utilities-other.html")

class OcrApiHandler(BaseHandler):
    """docstring for OcrApiHandler"""
    def get(self):
        pass

    async def post(self):
        pic = self.get_argument("pic")
        realname = self.get_argument("realname")

        if not realname or not pic:
            raise tornado.web.HTTPError(400, "program down")

        if realname not in await self.queryuser("SELECT user_name FROM users"):
            next_id = await self.queryone("SELECT max(id) FROM users")
            await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
                                int(next_id.max)+1, 
                                str(realname),
                                1)
        else:
            await self.execute("UPDATE users SET call = (call + 1) "
                                "WHERE user_name = %s",
                                realname)

        # ocrAi = ocr.OCR()
        # self.write(ocrAi.general_ocr(pic))
        result = await self.ocrInstant(pic)
        self.write(result)


class PythonApiHandler(BaseHandler):
    """docstring for PythonApiHandler"""
    def get(self):
        realname = self.get_argument("realname")
        query = self.get_argument("query")

        if not realname or not query:
            raise tornado.web.HTTPError(400, "program down")

        try:
            cmd = "sh ~/Downloads/work/run_similarity.sh {} {}".format(query, realname)
            subprocess.run(cmd, shell=True)
        except Exception as e:
            raise tornado.web.HTTPError(400, "program down")
        else:
            pass

class SimilarityApiHandler(BaseHandler):
    """docstring for PythonApiHandler"""
    def get(self):
        pass

    async def post(self):
        realname = self.get_argument("realname")
        query = self.get_argument("query")
        sogou_text = self.get_argument("sogou_text")
        other_text = self.get_argument("other_text")

        # result
        ke_result = 0
        score = 0
        final = 0

        if not realname or not query or not sogou_text or not other_text:
            raise tornado.web.HTTPError(400, "program down")

        if realname not in await self.queryuser("SELECT user_name FROM users"):
            next_id = await self.queryone("SELECT max(id) FROM users")
            await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
                                int(next_id.max)+1, 
                                str(realname),
                                1)
        else:
            await self.execute("UPDATE users SET call = (call + 1) "
                                "WHERE user_name = %s",
                                realname)

        if query and query in sogou_text:
            self.write("1")
            self.finish()
        else:
            if "\n" in sogou_text:
                sogou_text = sogou_text.replace("\n", " ")
            
            with BertClient(port=4444, port_out=4445) as bc:
                score = bc.encode([query + " ||| " + sogou_text])[0][1]

            ke4webAI = ke4web()
            ke_result = ke4webAI.simCal(sogou_text, other_text, self.application.model)

            if float(score) < 0.5 and float(ke_result[0]) < 0.7 and float(ke_result[1]) < 0.7:
                final = 0
            else:
                final = 1

            self.write("{}".format(final))


class SimUrlencodeApiHandler(BaseHandler):
    """docstring for PythonApiHandler"""
    def get(self):
        pass

    async def post(self):
        realname = self.get_argument("realname")
        query = self.get_argument("text_a")
        context = self.get_argument("text_b")
        threshold = self.get_argument("threshold")

        print("{} || {}".format(query, context))
        print("{} || {}".format(parse.unquote(query), parse.unquote(context)))

        query = parse.unquote(query)
        context = parse.unquote(context)

        threshold = eval(threshold)
        #query = eval(query)
        context = eval(context)
        if not realname or not query or not context or not threshold:
            raise tornado.web.HTTPError(400, "Program down")

        if not isinstance(threshold, list):
            raise tornado.web.HTTPError(400, "Threshold should be a list.")

        if not isinstance(query, list) and not isinstance(context, list):
            raise tornado.web.HTTPError(400, "text_a or text_b should be a list.")

        if realname not in await self.queryuser("SELECT user_name FROM users"):
            next_id = await self.queryone("SELECT max(id) FROM users")
            await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
                                int(next_id.max)+1, 
                                str(realname),
                                1)
        else:
            await self.execute("UPDATE users SET call = (call + 1) "
                                "WHERE user_name = %s",
                                realname)
        encode_list = []
        ke_result = []
        final = []
        ke4webAI = ke4web()
        if isinstance(query, list):
            for item in query:
                encode_list.append(item + " ||| " + context)
                ke_result.append(ke4webAI.simCal(item, context, self.application.model))
        elif isinstance(context, list):
            for item in context:
                encode_list.append(query + " ||| " + item)
                ke_result.append(ke4webAI.simCal(query, item, self.application.model))

        with BertClient(port=4447, port_out=4448) as bc:
            score_list = bc.encode(encode_list)

        for x, y in zip(score_list, ke_result):
            if float(x[1]) > float(threshold[0]) and float(y[0]) > float(threshold[1]) and float(y[1]) > float(threshold[2]):
                final.append(1)
            else:
                final.append(0)

        print(score_list)
        print(ke_result)
        self.write("{}".format(final))


class PicSimApiHandler(BaseHandler):
    """docstring for PicSimApiHandler"""
    def get(self):
        pass

    async def post(self):
        realname = self.get_argument("realname")
        template = self.get_argument("pic_a")
        target = self.get_argument("pic_b")

        if not realname or not template or not target:
            raise tornado.web.HTTPError(400, "program down")

        if realname not in await self.queryuser("SELECT user_name FROM users"):
            next_id = await self.queryone("SELECT max(id) FROM users")
            await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
                                int(next_id.max)+1, 
                                str(realname),
                                1)
        else:
            await self.execute("UPDATE users SET call = (call + 1) "
                                "WHERE user_name = %s",
                                realname)

        picSimAi = MatchTemplate(template, target)
        result = picSimAi.match()

        self.write("{}".format(result))


class TemplateMatchApiHandler(BaseHandler):
    """docstring for TemplateMatchApiHandler"""
    def get(self):
        pass

    async def post(self):
        realname = self.get_argument("realname")
        template = self.get_argument("template")
        target = self.get_argument("target")
        method = self.get_argument("type")

        if not realname or not template or not target or not method:
            raise tornado.web.HTTPError(400, "program down")

        if realname not in await self.queryuser("SELECT user_name FROM users"):
            next_id = await self.queryone("SELECT max(id) FROM users")
            await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
                                int(next_id.max)+1, 
                                str(realname),
                                1)
        else:
            await self.execute("UPDATE users SET call = (call + 1) "
                                "WHERE user_name = %s",
                                realname)

        picMatchAi = picMatchTemplate()
        if method == "base64":   
            result = picMatchAi.match(template, target)
        elif method == "url":
            pic_a = Image.open(BytesIO(requests.get(template).content)).convert("RGB")
            pic_b = Image.open(BytesIO(requests.get(target).content)).convert("RGB")
            if pic_a.size[0] > pic_b.size[0]:
                pic_a = pic_a.resize(pic_b.size)
            else:
                pic_b = pic_b.resize(pic_a.size)
            pic_a = np.array(pic_a)
            pic_b = np.array(pic_b)
            result = picMatchAi.method(pic_a, pic_b)
        else:
            raise tornado.web.HTTPError(400, "Argument type Error")

        self.write(result)

class GDetectApiHandler(BaseHandler):
    def get(self):
        pass

    async def post(self):
        pic = self.get_argument("pic")
        realname = self.get_argument("realname")

        if not realname or not pic:
            raise tornado.web.HTTPError(400, "program down")

        if realname not in await self.queryuser("SELECT user_name FROM users"):
            next_id = await self.queryone("SELECT max(id) FROM users")
            await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
                                int(next_id.max)+1,
                                str(realname),
                                1)
        else:
            await self.execute("UPDATE users SET call = (call + 1) "
                                "WHERE user_name = %s",
                                realname)

        result = detect.detect(eval(pic), self.application.gModel)

        self.write(str(result))

class UIDetectApiHandler(BaseHandler):
    def get(self):
        pass

    async def post(self):
        pic = self.get_argument("pic")
        realname = self.get_argument("realname")

        if not realname or not pic:
            raise tornado.web.HTTPError(400, "program down")

        if realname not in await self.queryuser("SELECT user_name FROM users"):
            next_id = await self.queryone("SELECT max(id) FROM users")
            await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
                                int(next_id.max)+1,
                                str(realname),
                                1)
        else:
            await self.execute("UPDATE users SET call = (call + 1) "
                                "WHERE user_name = %s",
                                realname)

        result = ui_detect.detect(eval(pic), self.application.uiModel)

        self.write(str(result))

class GTextDetectApiHandler(BaseHandler):

    async def post(self):
        text = self.get_argument("text")
        realname = self.get_argument("realname")

        if not realname or not text:
            raise tornado.web.HTTPError(400, "program down")

        if realname not in await self.queryuser("SELECT user_name FROM users"):
            next_id = await self.queryone("SELECT max(id) FROM users")
            await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
                                int(next_id.max)+1,
                                str(realname),
                                1)
        else:
            await self.execute("UPDATE users SET call = (call + 1) "
                                "WHERE user_name = %s",
                                realname)

        detect = gtextdetect()
        result = detect.predict(sentence=text, model=self.application.gTextModel)

        self.write(str(result))

class EntryPageHandler(BaseHandler):
    async def get(self, slug):
        entry = await self.queryone("SELECT * FROM entries WHERE slug = %s", slug)
        if not entry:
            raise tornado.web.HTTPError(404)
        self.render("pages/entry.html", entry=entry)
        
        
async def main():
    tornado.options.parse_command_line()

    # Create the global connection pool.
    async with aiopg.create_pool(
        host=options.db_host,
        port=options.db_port,
        user=options.db_user,
        password=options.db_password,
        dbname=options.db_database,
    ) as db:
        await maybe_create_tables(db)
        app = Application(db)
        app.listen(options.port)

        shutdown_event = tornado.locks.Event()
        await shutdown_event.wait()


if __name__ == "__main__":
    tornado.ioloop.IOLoop.current().run_sync(main)
