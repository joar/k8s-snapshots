import json
import os

import pykube
import structlog
from googleapiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials
from oauth2client.client import GoogleCredentials

_logger = structlog.get_logger()


class Context:
    def __init__(self, config=None):
        self.config = config
        self._kube_config = None

    @property
    def kube_config(self):
        if self._kube_config is None:
            self._kube_config = self.load_kube_config()

        return self._kube_config

    def load_kube_config(self):
        cfg = None

        kube_config_file = self.config.get('kube_config_file')

        if kube_config_file:
            _logger.info('kube-config.from-file', file=kube_config_file)
            cfg = pykube.KubeConfig.from_file(kube_config_file)

        if not cfg:
            # See where we can get it from.
            default_file = os.path.expanduser('~/.kube/config')
            if os.path.exists(default_file):
                _logger.info(
                    'kube-config.from-file.default',
                    file=default_file)
                cfg = pykube.KubeConfig.from_file(default_file)

        # Maybe we are running inside Kubernetes.
        if not cfg:
            _logger.info('kube-config.from-service-account')
            cfg = pykube.KubeConfig.from_service_account()

        return cfg

    def kube_client(self):
        return pykube.HTTPClient(self.kube_config)

    def gcloud(self, version: str='v1'):
        """
        Get a configured Google Compute API Client instance.

        Note that the Google API Client is not threadsafe. Cache the instance locally
        if you want to avoid OAuth overhead between calls.

        Parameters
        ----------
        version
            Compute API version
        """
        SCOPES = 'https://www.googleapis.com/auth/compute'
        credentials = None

        if self.config.get('gcloud_json_keyfile_name'):
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                self.config.get('gcloud_json_keyfile_name'),
                scopes=SCOPES)

        if self.config.get('gcloud_json_keyfile_string'):
            keyfile = json.loads(self.config.get('gcloud_json_keyfile_string'))
            credentials = ServiceAccountCredentials.from_json_keyfile_dict(
                keyfile, scopes=SCOPES)

        if not credentials:
            credentials = GoogleCredentials.get_application_default()

        if not credentials:
            raise RuntimeError("Auth for Google Cloud was not configured")

        compute = discovery.build(
            'compute',
            version,
            credentials=credentials,
            # https://github.com/google/google-api-python-client/issues/299#issuecomment-268915510
            cache_discovery=False
        )
        return compute
