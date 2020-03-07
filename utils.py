# from bert_serving.client import BertClient
# from ke.ke4web import ke4web
# from ke.evalKE import evalKE
# from yolov3ocr import ocr
# from cvTM.cvMatchTemplate import MatchTemplate
# from cvTM.cvPicMatch import picMatchTemplate
# from gDetect import detect
# from uiDetect import ui_detect
# from gTextDetect.model import detect as gtextdetect
# from utils.whiteCal import pixel_cal

# class OcrApiHandler(BaseHandler):
#     """docstring for OcrApiHandler"""
#     def get(self):
#         pass

#     async def post(self):
#         pic = self.get_argument("pic")
#         realname = self.get_argument("realname")

#         if not realname or not pic:
#             raise tornado.web.HTTPError(400, "program down")

#         if realname not in await self.queryuser("SELECT user_name FROM users"):
#             next_id = await self.queryone("SELECT max(id) FROM users")
#             await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
#                                 int(next_id.max)+1, 
#                                 str(realname),
#                                 1)
#         else:
#             await self.execute("UPDATE users SET call = (call + 1) "
#                                 "WHERE user_name = %s",
#                                 realname)

#         # ocrAi = ocr.OCR()
#         # self.write(ocrAi.general_ocr(pic))
#         result = await self.ocrInstant(pic)
#         self.write(result)


# class SimilarityApiHandler(BaseHandler):
#     """docstring for PythonApiHandler"""
#     def get(self):
#         pass

#     async def post(self):
#         realname = self.get_argument("realname")
#         query = self.get_argument("query")
#         sogou_text = self.get_argument("sogou_text")
#         other_text = self.get_argument("other_text")

#         # result
#         ke_result = 0
#         score = 0
#         final = 0

#         if not realname or not query or not sogou_text or not other_text:
#             raise tornado.web.HTTPError(400, "program down")

#         if realname not in await self.queryuser("SELECT user_name FROM users"):
#             next_id = await self.queryone("SELECT max(id) FROM users")
#             await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
#                                 int(next_id.max)+1, 
#                                 str(realname),
#                                 1)
#         else:
#             await self.execute("UPDATE users SET call = (call + 1) "
#                                 "WHERE user_name = %s",
#                                 realname)

#         if query and query in sogou_text:
#             self.write("1")
#             self.finish()
#         else:
#             if "\n" in sogou_text:
#                 sogou_text = sogou_text.replace("\n", " ")
            
#             with BertClient(port=4444, port_out=4445) as bc:
#                 score = bc.encode([query + " ||| " + sogou_text])[0][1]

#             ke4webAI = ke4web()
#             ke_result = ke4webAI.simCal(sogou_text, other_text, self.application.model)

#             if float(score) < 0.5 and float(ke_result[0]) < 0.7 and float(ke_result[1]) < 0.7:
#                 final = 0
#             else:
#                 final = 1

#             self.write("{}".format(final))


# class SimUrlencodeApiHandler(BaseHandler):
#     """docstring for PythonApiHandler"""
#     def get(self):
#         pass

#     async def post(self):
#         realname = self.get_argument("realname")
#         query = self.get_argument("text_a")
#         context = self.get_argument("text_b")
#         threshold = self.get_argument("threshold")

#         print("{} || {}".format(query, context))
#         print("{} || {}".format(parse.unquote(query), parse.unquote(context)))

#         query = parse.unquote(query)
#         context = parse.unquote(context)

#         threshold = eval(threshold)
#         #query = eval(query)
#         context = eval(context)
#         if not realname or not query or not context or not threshold:
#             raise tornado.web.HTTPError(400, "Program down")

#         if not isinstance(threshold, list):
#             raise tornado.web.HTTPError(400, "Threshold should be a list.")

#         if not isinstance(query, list) and not isinstance(context, list):
#             raise tornado.web.HTTPError(400, "text_a or text_b should be a list.")

#         if realname not in await self.queryuser("SELECT user_name FROM users"):
#             next_id = await self.queryone("SELECT max(id) FROM users")
#             await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
#                                 int(next_id.max)+1, 
#                                 str(realname),
#                                 1)
#         else:
#             await self.execute("UPDATE users SET call = (call + 1) "
#                                 "WHERE user_name = %s",
#                                 realname)
#         encode_list = []
#         ke_result = []
#         final = []
#         ke4webAI = ke4web()
#         if isinstance(query, list):
#             for item in query:
#                 encode_list.append(item + " ||| " + context)
#                 ke_result.append(ke4webAI.simCal(item, context, self.application.model))
#         elif isinstance(context, list):
#             for item in context:
#                 encode_list.append(query + " ||| " + item)
#                 ke_result.append(ke4webAI.simCal(query, item, self.application.model))

#         with BertClient(port=4447, port_out=4448) as bc:
#             score_list = bc.encode(encode_list)

#         for x, y in zip(score_list, ke_result):
#             if float(x[1]) > float(threshold[0]) and float(y[0]) > float(threshold[1]) and float(y[1]) > float(threshold[2]):
#                 final.append(1)
#             else:
#                 final.append(0)

#         print(score_list)
#         print(ke_result)
#         self.write("{}".format(final))


# class PicSimApiHandler(BaseHandler):
#     """docstring for PicSimApiHandler"""
#     def get(self):
#         pass

#     async def post(self):
#         realname = self.get_argument("realname")
#         template = self.get_argument("pic_a")
#         target = self.get_argument("pic_b")

#         if not realname or not template or not target:
#             raise tornado.web.HTTPError(400, "program down")

#         if realname not in await self.queryuser("SELECT user_name FROM users"):
#             next_id = await self.queryone("SELECT max(id) FROM users")
#             await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
#                                 int(next_id.max)+1, 
#                                 str(realname),
#                                 1)
#         else:
#             await self.execute("UPDATE users SET call = (call + 1) "
#                                 "WHERE user_name = %s",
#                                 realname)

#         picSimAi = MatchTemplate(template, target)
#         result = picSimAi.match()

#         self.write("{}".format(result))


# class TemplateMatchApiHandler(BaseHandler):
#     """docstring for TemplateMatchApiHandler"""
#     def get(self):
#         pass

#     async def post(self):
#         realname = self.get_argument("realname")
#         template = self.get_argument("template")
#         target = self.get_argument("target")
#         method = self.get_argument("type")

#         if not realname or not template or not target or not method:
#             raise tornado.web.HTTPError(400, "program down")

#         if realname not in await self.queryuser("SELECT user_name FROM users"):
#             next_id = await self.queryone("SELECT max(id) FROM users")
#             await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
#                                 int(next_id.max)+1, 
#                                 str(realname),
#                                 1)
#         else:
#             await self.execute("UPDATE users SET call = (call + 1) "
#                                 "WHERE user_name = %s",
#                                 realname)

#         picMatchAi = picMatchTemplate()
#         if method == "base64":   
#             result = picMatchAi.match(template, target)
#         elif method == "url":
#             pic_a = Image.open(BytesIO(requests.get(template).content)).convert("RGB")
#             pic_b = Image.open(BytesIO(requests.get(target).content)).convert("RGB")
#             if pic_a.size[0] > pic_b.size[0]:
#                 pic_a = pic_a.resize(pic_b.size)
#             else:
#                 pic_b = pic_b.resize(pic_a.size)
#             pic_a = np.array(pic_a)
#             pic_b = np.array(pic_b)
#             result = picMatchAi.method(pic_a, pic_b)
#         else:
#             raise tornado.web.HTTPError(400, "Argument type Error")

#         self.write(result)

# class GDetectApiHandler(BaseHandler):
#     def get(self):
#         pass

#     async def post(self):
#         pic = self.get_argument("pic")
#         realname = self.get_argument("realname")

#         if not realname or not pic:
#             raise tornado.web.HTTPError(400, "program down")

#         if realname not in await self.queryuser("SELECT user_name FROM users"):
#             next_id = await self.queryone("SELECT max(id) FROM users")
#             await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
#                                 int(next_id.max)+1,
#                                 str(realname),
#                                 1)
#         else:
#             await self.execute("UPDATE users SET call = (call + 1) "
#                                 "WHERE user_name = %s",
#                                 realname)

#         result = detect.detect(eval(pic), self.application.gModel)

#         self.write(str(result))

# class UIDetectApiHandler(BaseHandler):
#     def get(self):
#         pass

#     async def post(self):
#         pic = self.get_argument("pic")
#         realname = self.get_argument("realname")

#         if not realname or not pic:
#             raise tornado.web.HTTPError(400, "program down")

#         if realname not in await self.queryuser("SELECT user_name FROM users"):
#             next_id = await self.queryone("SELECT max(id) FROM users")
#             await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
#                                 int(next_id.max)+1,
#                                 str(realname),
#                                 1)
#         else:
#             await self.execute("UPDATE users SET call = (call + 1) "
#                                 "WHERE user_name = %s",
#                                 realname)

#         result = ui_detect.detect(eval(pic), self.application.uiModel)

#         self.write(str(result))

# class GTextDetectApiHandler(BaseHandler):

#     async def post(self):
#         text = self.get_argument("text")
#         realname = self.get_argument("realname")

#         if not realname or not text:
#             raise tornado.web.HTTPError(400, "program down")

#         if realname not in await self.queryuser("SELECT user_name FROM users"):
#             next_id = await self.queryone("SELECT max(id) FROM users")
#             await self.execute("INSERT INTO users VALUES (%s, %s, %s)", 
#                                 int(next_id.max)+1,
#                                 str(realname),
#                                 1)
#         else:
#             await self.execute("UPDATE users SET call = (call + 1) "
#                                 "WHERE user_name = %s",
#                                 realname)

#         detect = gtextdetect()
#         result = detect.predict(sentence=text, model=self.application.gTextModel)

#         self.write(str(result))

# class GetBlankRate(BaseHandler):
#     def get(self):
#         pass

#     async def post(self):
#         print("blank rate")
#         realname = self.get_argument("realname")
#         pic_str = self.get_argument("pic")
#         method = self.get_argument("type")

#         if not realname or not pic_str or  not method:
#             raise tornado.web.HTTPError(400, "program down")

#         if realname not in await self.queryuser("SELECT user_name FROM users"):
#             next_id = await self.queryone("SELECT max(id) FROM users")
#             await self.execute("INSERT INTO users VALUES (%s, %s, %s)",
#                                 int(next_id.max)+1,
#                                 str(realname),
#                                 1)
#         else:
#             await self.execute("UPDATE users SET call = (call + 1) "
#                                 "WHERE user_name = %s",
#                                 realname)

#         pixel = pixel_cal()
#         if method == "0":
#             image = pixel.change_to_thumbnail(pixel.base64_pil(pic_str))
#             blank_rate = pixel.pil_cal(image, image_display=False)
#         elif method == "1":
#             blank_rate = pixel.skimage_cal(pixel.base64_pil(pic_str))
#         else:
#             raise tornado.web.HTTPError(400, "Argument type Error")

#         self.write(str(blank_rate))