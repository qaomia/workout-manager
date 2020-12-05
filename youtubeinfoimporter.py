import requests
import json
import logging

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

    # youtubeVideoUrl = 'https://www.youtube.com/watch?v={0}'

    def __init__(self, api_key_filepath):
        self.api_key_filepath = api_key_filepath
        self.api_key = self.get_api_key()
        self.youtube_channel_api_url = YoutubeInfoImporter.YOUTUBE_CHANNEL_API_URL.replace("<api_key>", self.api_key)
        self.youtube_search_api_url = YoutubeInfoImporter.YOUTUBE_SEARCH_API_URL.replace("<api_key>", self.api_key)

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

    def get_channel_videos_ids(self, channel_id):
        """
            Retrieves videos ids of a given channel id.
        :param channel_id:
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
            url = ''.join((self.youtube_search_api_url, f'channelId={channel_id}&part=id&order=date&type=video&maxResults=50'))

            if next_page_token:
                url = ''.join((url, "&pageToken=", next_page_token))

            # Send request
            response = self.send_request(url)

            # Fetch videos ids
            if response["items"]:
                new_videos = [i["id"]["videoId"] for i in response["items"]]
                list_videos.extend(new_videos)
                # Update loop condition
                next_page_token = response["nextPageToken"]
            else:
                log.debug("No more video to fetch.")
                break

        log.info(f"{len(list_videos)} were found for channel {channel_id} using {nb_iter} iterations.")
        log.debug(f"Videos id of channel: {channel_id}: {list_videos}")
        return list_videos


if __name__ == '__main__':
    yt = YoutubeInfoImporter("D:\\git\\workout-manager\\api_key.txt")
    ch_id = yt.get_channel_id("blogilates")
    v = yt.get_channel_videos_ids(ch_id)
    print(len(v))
