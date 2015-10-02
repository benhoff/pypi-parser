import re
import asyncio
import requests

from simpleyapsy import IPlugin


DEFAULT_PYPI = 'https://pypi.python.org/pypi'
PYPI_RE = re.compile('''^(?:(?P<pypi>https?://[^/]+/pypi)/)?
                        (?P<name>[-A-Za-z0-9_.]+)
                        (?:/(?P<version>[-A-Za-z0-9.]+))?$''', re.X)

# NOTE: not used
# SEARCH_URL = 'https://pypi.python.org/pypi?%3Aaction=search&term={query}'


class PyPiParser(IPlugin):
    # TODO: change to Regex Plugin class
    def __init__(self):
        super().__init__()
        self.name = 'pypi-parser'
        self.matches = [re.compile('pypi'), PYPI_RE]

    def __call__(self, name):
        package = get_package(name)
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, package.data)
        yield from future
        return package.downloads, package.average_downloads


@asyncio.coroutine
def get_package(name_or_url, client=None):
    m = PYPI_RE.match(name_or_url)
    if not m:
        return None
    pypi_url = m.group('pypi') or DEFAULT_PYPI
    name = m.group('name')
    return Package(name, pypi_url=pypi_url, client=client)


class Package(object):
    def __init__(self, name, client=None, pypi_url=DEFAULT_PYPI):
        self.client = client or requests.Session()
        self.name = name
        self.url = '{pypi_url}/{name}/json'.format(pypi_url=pypi_url,
                                                   name=name)

    @asyncio.coroutine
    def data(self):
        resp = self.client.get(self.url)
        if resp.status_code == 404:
            raise Exception('Package not found')
        return resp.json()

    @lazy_property
    def versions(self):
        """Return a list of versions, sorted by release datae."""
        return [k for k, v in self.release_info]

    @lazy_property
    def version_downloads(self):
        """Return a dictionary of version:download_count pairs."""
        ret = OrderedDict()
        for release, info in self.release_info:
            download_count = sum(file_['downloads'] for file_ in info)
            ret[release] = download_count
        return ret

    @property
    def release_info(self):
        release_info = self.data['releases']
        # filter out any versions that have no releases
        filtered = [(ver, releases) for ver, releases in release_info.items()
                    if len(releases) > 0]
        # sort by first upload date of each release
        return sorted(filtered, key=lambda x: x[1][0]['upload_time'])

    @lazy_property
    def version_dates(self):
        ret = OrderedDict()
        for release, info in self.release_info:
            if info:
                upload_time = dateparse(info[0]['upload_time'])
                ret[release] = upload_time
        return ret

    def chart(self):
        def style_version(version):
            return style(version, fg='cyan', bold=True)

        data = OrderedDict()
        for version, dl_count in self.version_downloads.items():
            date = self.version_dates.get(version)
            date_formatted = ''
            if date:
                date_formatted = time.strftime(DATE_FORMAT,
                    self.version_dates[version].timetuple())
            key = "{0:20} {1}".format(
                style_version(version),
                date_formatted
            )
            data[key] = dl_count
        return bargraph(data, max_key_width=20 + _COLOR_LEN + _BOLD_LEN)

    @lazy_property
    def downloads(self):
        """Total download count.

        :return: A tuple of the form (version, n_downloads)
        """
        return sum(self.version_downloads.values())

    @lazy_property
    def max_version(self):
        """Version with the most downloads.

        :return: A tuple of the form (version, n_downloads)
        """
        data = self.version_downloads
        if not data:
            return None, 0
        return max(data.items(), key=lambda item: item[1])

    @lazy_property
    def min_version(self):
        """Version with the fewest downloads."""
        data = self.version_downloads
        if not data:
            return (None, 0)
        return min(data.items(), key=lambda item: item[1])

    @lazy_property
    def average_downloads(self):
        """Average number of downloads."""
        return int(self.downloads / len(self.versions))

    @property
    def author(self):
        return self.data['info'].get('author')

    @property
    def description(self):
        return self.data['info'].get('description')

    @property
    def summary(self):
        return self.data['info'].get('summary')

    @property
    def author_email(self):
        return self.data['info'].get('author_email')

    @property
    def maintainer(self):
        return self.data['info'].get('maintainer')

    @property
    def maintainer_email(self):
        return self.data['info'].get('maintainer_email')

    @property
    def license(self):
        return self.data['info'].get('license')

    @property
    def downloads_last_day(self):
        return self.data['info']['downloads']['last_day']

    @property
    def downloads_last_week(self):
        return self.data['info']['downloads']['last_week']

    @property
    def downloads_last_month(self):
        return self.data['info']['downloads']['last_month']

    @property
    def package_url(self):
        return self.data['info']['package_url']

    @property
    def home_page(self):
        return self.data['info'].get('home_page')

    @property
    def docs_url(self):
        return self.data['info'].get('docs_url')

    def __repr__(self):
        return '<Package(name={0!r})>'.format(self.name)
