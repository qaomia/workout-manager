import requests
import json
import logging
import math
from rfc3339 import rfc3339
import datetime
import isodate
import pprint

# Logs in console
logging.basicConfig(level=logging.DEBUG)

# logger
log = logging.getLogger(__name__)


class YoutubeInfoImporter:
    """
        Calls Youtube API to get videos information.
        An API KEY from Google is required. See https://console.developers.google.com.
        Inspired from https://github.com/dsebastien/youtubeChannelVideosFinder/blob/master/youtubeChannelVideosFinder.py
    """

    YOUTUBE_API_URL = 'https://www.googleapis.com/youtube/v3/'
    YOUTUBE_CHANNEL_API_URL = ''.join((YOUTUBE_API_URL, 'channels?key=<api_key>&'))
    YOUTUBE_SEARCH_API_URL = ''.join((YOUTUBE_API_URL, 'search?key=<api_key>&'))
    YOUTUBE_VIDEO_DETAILS_API_URL = ''.join((YOUTUBE_API_URL, 'videos?key=<api_key>&part=snippet,contentDetails&'))
    YOUTUBE_VIDEO_URL = 'https://www.youtube.com/watch?v=<video_id>'

    def __init__(self, api_key_filepath):
        self.api_key_filepath = api_key_filepath
        self.api_key = self.get_api_key()
        self.youtube_channel_api_url = YoutubeInfoImporter.YOUTUBE_CHANNEL_API_URL.replace("<api_key>", self.api_key)
        self.youtube_search_api_url = YoutubeInfoImporter.YOUTUBE_SEARCH_API_URL.replace("<api_key>", self.api_key)
        self.youtube_video_details_api_url = YoutubeInfoImporter.YOUTUBE_VIDEO_DETAILS_API_URL.replace("<api_key>", self.api_key)
        self.videos_dict = {}

    # ---------------------------------------------- #

    def get_api_key(self):
        """
        Reads an API key from a text file.
        :return: string API key
        """
        with open(self.api_key_filepath, 'r') as reader:
            # Read & print the entire file
            api_key = reader.read()
        return api_key

    # ---------------------------------------------- #

    def get_videos_dict(self):
        """
        Prints nicely videos dict
        :return:
        """
        pp = pprint.PrettyPrinter(depth=4)
        pp.pprint(self.videos_dict)

    # ---------------------------------------------- #

    @staticmethod
    def send_request(url):
        """
        Send a request to an API and parses its response in JSON.
        :param url: str URL to request
        :return: JSON response
        """
        log.debug(f"Request: {url}")

        log.info('Sending request')
        response = requests.get(url)

        log.info('Parsing the response')
        response_as_json = response.json()
        log.debug(f'Response: {json.dumps(response_as_json, indent=4)}')

        if response.status_code != 200:
            log.error(f'Response: {json.dumps(response_as_json, indent=4)}')
            raise ValueError(f"Error while requesting API, status_code: {response.status_code}.")

        return response_as_json

    # ---------------------------------------------- #

    def get_channel_id(self, channel_name):
        """
        Retrieves channel ID of a Youtube channel.
        :param channel_name: str name of the channel
        :return: str id of the channel
        """
        log.info(f'Searching channel id for channel: {channel_name}')

        url = ''.join((self.youtube_channel_api_url, f'forUsername={channel_name}&part=id'))
        response_as_json = self.send_request(url)

        log.info('Extracting the channel id')
        if response_as_json['pageInfo'].get('totalResults') > 0:
            returned_info = response_as_json['items'][0]
            channel_id = returned_info.get('id')
            log.debug(f'Channel id found: {str(channel_id)}')
        else:
            log.error('Response received but it contains no item')
            raise ValueError('The channel id could not be retrieved. Make sure that the channel name is correct')

        if response_as_json['pageInfo'].get('totalResults') > 1:
            log.warning(
                'Multiple channels were received in the response. If this happens, something can probably be improved '
                'around here')

        return channel_id

    # ---------------------------------------------- #

    def get_channel_videos_ids(self, channel_id, published_after=None):
        """
        Retrieves videos ids of a given channel id. If published_after is not specified, it fetches all the videos
        of the channel.
        :param channel_id: str, id of the channel to fetch
        :param published_after: str, date in the format YYYY-MM-DD to fetch videos after this given date.
        :return:
        """

        log.info(f"Fetching videos id of channel {channel_id}...")
        next_page_token = None
        list_videos = []
        nb_iter = 0
        while True:
            # Increment number of iterations
            nb_iter += 1

            # Build url string
            url = ''.join((self.youtube_search_api_url, f'channelId={channel_id}&part=id&order=date&type=video'
                                                        f'&maxResults=50'))

            if next_page_token:
                url = ''.join((url, "&pageToken=", next_page_token))

            if published_after:
                log.debug('Converting timestamps to RFC3339 format')
                try:
                    published_after_date = datetime.datetime.strptime(published_after, "%Y-%m-%d")
                    published_after_rfc3339 = rfc3339(published_after_date, utc=True)
                    url = ''.join((url, "&publishedAfter=", published_after_rfc3339))
                except ValueError:
                    raise ValueError("Incorrect data format, should be YYYY-MM-DD")
            # Send request
            response = self.send_request(url)

            # Determine max number of iterations at the first call
            nb_videos = response["pageInfo"]["totalResults"]
            max_iter = math.ceil(nb_videos/50)
            log.debug(f"There are {nb_videos} videos to fetch. Max number of iterations is {max_iter}.")

            # Fetch videos ids
            if response["items"]:
                new_videos = [i["id"]["videoId"] for i in response["items"]]
                list_videos.extend(new_videos)

            # Loop break condition: no videos or too many iterations. The later is a failsafe for API calls quota.
            if not response["items"] or nb_iter >= max_iter or "nextPageToken" not in response:
                log.debug("No more video to fetch.")
                break

            # Update loop condition
            next_page_token = response["nextPageToken"]

        log.info(f"{len(list_videos)} were found for channel {channel_id} using {nb_iter} iterations.")
        log.debug(f"Videos id of channel: {channel_id}: {list_videos}")
        return list_videos

    # ---------------------------------------------- #

    def get_video_info(self, video_id, limit_description=100):
        """
        Get video information such as title and description.
        :param video_id: str, id of the video
        :param limit_description: int, maximum number of characters saved within video description
        :return: dict
        """
        log.info(f"Fetching information for video {video_id}...")

        # Build url string
        url = ''.join((self.youtube_video_details_api_url, f'id={video_id}'))

        # Send request
        response = self.send_request(url)

        if response["items"]:
            video_info = {
                "title": response["items"][0]["snippet"]["title"],
                "publishedAt": response["items"][0]["snippet"]["publishedAt"],
                "description": response["items"][0]["snippet"]["description"][:limit_description],
                "url": self.YOUTUBE_VIDEO_URL.replace("<video_id>", video_id),
                "tags": response["items"][0]["snippet"]["tags"],
                "duration": isodate.parse_duration(response["items"][0]["contentDetails"]["duration"])
            }

            return video_info

        log.error(f"No information found for video {video_id}")
        raise ValueError(f"No information found for video {video_id}")

    # ---------------------------------------------- #

    def import_videos_from_channel(self, channel_name, channel_id=None, published_after=None):
        """
        Imports videos from a channel.
        :param channel_name: str, Name of the channel. Used to look for the channel id if not provided.
        :param channel_id: str, id of the channel. Optional.
        :param published_after: str, optional date to restrain videos importation. Must respect the format YYYY-MM-DD.
        """
        if not channel_id:
            channel_id = yt.get_channel_id(channel_name)
        self.videos_dict[channel_id] = {"channel_title": channel_name, "videos": {}}
        videos = yt.get_channel_videos_ids(channel_id, published_after)
        for v_id in videos:
            self.videos_dict[channel_id]["videos"][v_id] = yt.get_video_info(v_id)

    # ---------------------------------------------- #


if __name__ == '__main__':
    yt = YoutubeInfoImporter("D:\\git\\workout-manager\\api_key.txt")
    yt.import_videos_from_channel("blogilates", published_after="2020-12-01")
    print(yt.get_videos_dict())

