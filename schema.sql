-- To create the database:
--   CREATE DATABASE sservice;
--   CREATE USER sservice WITH PASSWORD 'sservice';
--   GRANT ALL ON DATABASE sservice TO sservice;
--
-- To reload the tables:
--   psql -U sservice -d sservice < schema.sql

DROP TABLE IF EXISTS authors;
CREATE TABLE authors (
    id SERIAL PRIMARY KEY,
    real_name VARCHAR(100) NOT NULL,
    nick_name VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    hashed_password VARCHAR(100) NOT NULL
);

DROP TABLE IF EXISTS entries;
CREATE TABLE entries (
    id SERIAL PRIMARY KEY,
    author_id INT NOT NULL REFERENCES authors(id),
    slug VARCHAR(100) NOT NULL UNIQUE,
    title VARCHAR(512) NOT NULL,
    markdown TEXT NOT NULL,
    html TEXT NOT NULL,
    published TIMESTAMP NOT NULL,
    updated TIMESTAMP NOT NULL
);

CREATE INDEX ON entries (published);

DROP TABLE IF EXISTS users;
CREATE TABLE users (
	id SERIAL PRIMARY KEY,
	user_name VARCHAR(50) NOT NULL UNIQUE,
	call INT NOT NULL
);
