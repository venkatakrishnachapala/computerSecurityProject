import logging
import pprint
from http.cookies import SimpleCookie
from re import findall
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import requests

from Helper import write_msg

Urls = list[str]
WebPages = dict[str, list[str]]

DEFAULT_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/109.0.5414.119 Safari/537.36'

DEBUG = False
SQL_ERRORS = [
    "you have an error in your sql syntax",
    "mysql_fetch",
    "unclosed quotation mark",
    "pg_query",
    "sqlstate",
    "ORA-",
    "unexpected end of SQL command",
]

def contains_sql_error(text: str) -> bool:
    return any(err in text.lower() for err in SQL_ERRORS)

class Breakage(object):
    def __init__(self, urls: Urls, threshold: int,
                 verbose: bool = True, cookies: str = '',
                 user_agent: Optional[str] = None) -> None:
        self.urls = urls
        assert len(self.urls) > 0
        self.verbose = verbose
        self.threshold = threshold
        self.cookies = cookies
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.debug_counter = 0
        self.baseline()

    def baseline(self) -> None:
        raise NotImplementedError

    def broken(self, id=-1):
        raise NotImplementedError

    def print(self, message: str) -> None:
        if self.verbose:
            try:
                write_msg(message)
            except UnicodeEncodeError:
                write_msg(message.encode('ascii', 'ignore').decode())

    def pprint(self, x) -> None:
        if self.verbose:
            try:
                write_msg(pprint.pformat(x))
            except UnicodeEncodeError:
                write_msg(pprint.pformat(x).encode('ascii', 'ignore').decode())

    @staticmethod
    def cookiestr_to_dict(cookies: str) -> dict:
        cookie = SimpleCookie()
        cookie.load(cookies)
        return {k: v.value for k, v in cookie.items()}


class LengthBreakage(Breakage):
    def baseline(self):
        self.baselines = []
        for url in self.urls:
            self.print(url)
            baseline = self.get_webpage(url)
            if baseline is not None:
                content = baseline.read()
                self.print(f"baseline status code: {baseline.status}")
                self.print(f"baseline headers: {baseline.headers}")
                self.print(f"baseline content length: {len(content)}")
                self.baselines.append((baseline.status, content))
            else:
                self.baselines.append((None, b''))

    def broken(self, id=-1):
        broken = False
        for j, url in enumerate(self.urls):
            if self.is_broken(url, self.baselines[j]):
                self.print(f'{url} is broken')
                broken = True
        return broken

    def get_webpage(self, url: str) -> Any:
        req = Request(url, headers={'User-Agent': self.user_agent})
        try:
            return urlopen(req)
        except (HTTPError, URLError) as e:
            self.print(f"Error fetching {url}: {e}")
            return None

    def compare_broken(self, baseline_status: int, baseline_content: bytes, current_status: int, current_content: bytes) -> bool:
        if baseline_status != current_status:
            return True
        if len(current_content) < self.threshold:
            return True
        if contains_sql_error(current_content.decode(errors='ignore')):
            self.print("SQL error detected in content")
            return True
        return False

    def is_broken(self, url: str, baseline) -> bool:
        current = self.get_webpage(url)
        if current is None:
            return True
        return self.compare_broken(baseline[0], baseline[1], current.status, current.read())


class UrlBreakage(Breakage):
    def baseline(self):
        self.baselines = self.get_webpages()
        self.pprint(self.baselines)
        self.print(f"baseline checked URLs: {len(self.baselines)}")
        logging.debug(('dbfuzz', 'url_breakage', 'baseline', 'urls', 'length', len(self.baselines)))
        self.print(f"baseline total found links: {sum(len(v) for v in self.baselines.values())}")
        for url in self.baselines:
            for link in self.baselines[url]:
                logging.debug(('dbfuzz', 'url_breakage', 'baseline', 'link', url, link))

    def broken(self, id=-1):
        try:
            state = self.get_webpages()
            return self.broken_state(state, id)
        except (requests.exceptions.SSLError,
                requests.exceptions.TooManyRedirects,
                requests.exceptions.ConnectionError,
                requests.exceptions.InvalidURL):
            return True

    def get_webpages(self) -> WebPages:
        state = {}
        for url in self.urls:
            self.print(f"checking {url} {self.debug_counter}")
            try:
                headers = {'user-agent': self.user_agent}
                req = requests.get(url, cookies=self.cookiestr_to_dict(self.cookies), headers=headers)
                if contains_sql_error(req.text):
                    self.print(f"⚠️ SQL error found in {url}")
                links = findall('href="(.*?)"', req.content.decode(errors='ignore'))
                state[url] = links
                if DEBUG:
                    safe_url = url.translate({ord(i): None for i in ':/'})
                    with open(f'output/{safe_url}-{self.debug_counter}.html', 'w') as f:
                        f.write(req.text)
                self.debug_counter += 1
            except Exception as e:
                self.print(f"[ERROR] Failed to fetch {url}: {e}")
                raise
        return state

    def broken_state(self, state: WebPages, id: int) -> bool:
        total_links = 0
        missing_links = 0
        broken = False
        for url in self.baselines:
            if url not in state:
                self.print(f"Missing scan for {url}")
                broken = True
            else:
                for link in self.baselines[url]:
                    total_links += 1
                    if link not in state[url]:
                        self.print(f"Missing link {link} in {url}")
                        missing_links += 1
        if broken:
            return True
        frac_missing = float(missing_links) / float(total_links) if total_links else 0.0
        self.print(f"Missing: {missing_links} / {total_links} = {frac_missing:.3f}, threshold = {self.threshold / 100.0:.3f}")
        return frac_missing > (self.threshold / 100.0)