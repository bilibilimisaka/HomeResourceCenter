# serviceCMS
此网页为展示相似度以及ocr等服务而搭建，并提供专门服务的接口。

## install
搭建此网页首先需要安装依赖，依赖文件为requirements，执行以下命令。
-pip install -Ur requirements.txt

此外，需要安装数据库postgresql。

## database
数据库需要预先创立用户等，执行以下命令。
-CREATE DATABASE sservice;
-CREATE USER sservice WITH PASSWORD 'sservice';
-GRANT ALL ON DATABASE sservice TO sservice;

## api
网站入口为localhost:8888/index.html