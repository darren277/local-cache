# local-cache

## About

This project is a caching layer for locally running servers and web applications.

I have several local web applications I serve for myself for things like inventory management, information dashboards, etc. I wanted a way to cache some of the more frequently accessed responses from these applications so that I could serve them faster and not have to wait for the application to generate the response every time I visited the page.

## Structure

This repository contains three subdirectories, each with a different potential solution to this problem.

To summarize:
1. `browser-extensions`: A Firefox browser extension for caching responses from web applications.
2. `nginx-reverse-proxy`: A Docker container running an Nginx reverse proxy with caching enabled.
3. `python-proxy`: A Docker container running a Python proxy server with caching enabled.
