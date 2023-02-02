"""
This module contains the class to represent the GCP cloud provider, and the necessary functions.
"""

import logging
from pathlib import Path
import configparser
import json
import subprocess
from typing import Optional, Dict, List
import tempfile
from coguard_cli.discovery.cloud_discovery.cloud_provider_abc import CloudProvider
from coguard_cli import docker_dao
from coguard_cli.auth.auth_config import CoGuardCliConfig

class CloudProviderGCP(CloudProvider):
    """
    The class to represent GCP as a cloud provider.
    """

    def __init__(self):
        """
        The initialization function.
        """
        self._location_of_auth_json = ""
        self._projects = []

    def get_cloud_provider_name(self) -> str:
        """
        Overriding the abstract base class function.
        """
        return "gcp"

    def _get_account_id(self, account_ids: List[str]) -> str:
        """
        The prompt to let the user enter the profile intended to
        be used, assuming that there are multiple account ids to
        choose from.
        """
        assert len(account_ids) > 1, \
            "This function should only be called with a list containing more than 1 element."
        print("Multiple accounts detected: " + "\n".join(account_ids))
        inp = ""
        while inp not in account_ids:
            inp = input(f"Please type the account_id you wish to use (default: {account_ids[0]})")
            if not inp.strip():
                inp = account_ids[0]
            if inp not in account_ids:
                print("You typed an invalid profile name.")
        return inp


    def extract_credentials(self) -> Optional[Dict]:
        """
        Overriding the abstract base class function.
        """
        gcloud_config_path = Path(Path.home(), ".config", "gcloud")
        if not gcloud_config_path.exists():
            return None
        all_accounts = [
            d.name for d in gcloud_config_path.joinpath("legacy_credentials").iterdir()
            if d.is_dir()
        ]
        if not all_accounts:
            return None
        if len(all_accounts) == 1:
            account_id = all_accounts[0]
        else:
            account_id = self._get_account_id(all_accounts)
        self._location_of_auth_json = gcloud_config_path.joinpath(
            "legacy_credentials",
            account_id,
            "adc.json"
        )
        all_configs = [
            d for d in gcloud_config_path.joinpath("configurations").iterdir()
            if d.is_file()
        ]
        if not all_configs:
            logging.debug("The configurations folder was empty.")
            return None
        for config_file in all_configs:
            logging.debug("Trying to parse %s as a configuration",
                          config_file)
            config = configparser.ConfigParser(
                allow_no_value=True,
                strict = False
            )
            config.read(config_file)
            if "core" not in config.keys() or "account" not in config["core"].keys():
                logging.debug("The key \"core\" was not in the config.")
                continue
            logging.debug("The account id we are trying to match: %s",
                          account_id)
            logging.debug("The config core account value: %s",
                          config["core"]["account"] == account_id)
            if config["core"]["account"] == account_id:
                logging.debug("There was a match for account_id %s",
                              account_id)
                new_project = config["core"]["project"]
                if new_project:
                    self._projects.append(new_project)
        if not self._projects:
            return None
        result = None
        with self._location_of_auth_json.open() as auth_json:
            result = json.load(auth_json)
        return result

    def extract_iac_files_for_account(self,
                                      cli_conf: CoGuardCliConfig) -> Optional[str]:
        """
        Consider the abstract base class for documentation.
        """
        extracted_credentials = self.extract_credentials()
        if not extracted_credentials:
            logging.error("Could not extract the credentials for GCP.")
            return None
        temp_location = tempfile.mkdtemp(prefix="gcp_cloud_extraction")
        all_regions = self.get_all_regions()
        environment_variables = {
            "PROVIDER": self.get_cloud_provider_name(),
            "PROJECTS": ",".join(self._projects),
            "REGIONS": ",".join(all_regions),
            "CREDENTIALS": json.dumps(extracted_credentials)
        }
        res = docker_dao.terraformer_wrapper(
            temp_location,
            environment_variables,
            [],
            self.get_cloud_provider_name(),
            "google")
        if not res:
            return None
        return temp_location


    def get_all_regions(self):
        """
        Helper function to retrieve all regions.
        """
        default = [
            "us-east1",
            "us-east4",
            "us-central1",
            "us-west1",
            "europe-west4",
            "europe-west1",
            "europe-west3",
            "europe-west2",
            "asia-east1",
            "asia-southeast1",
            "asia-northeast1",
            "asia-south1",
            "australia-southeast1",
            "southamerica-east1",
            "asia-east2",
            "asia-northeast2",
            "asia-northeast3",
            "asia-south2",
            "asia-southeast2",
            "australia-southeast2",
            "europe-central2",
            "europe-north1",
            "europe-southwest1",
            "europe-west6",
            "europe-west8",
            "europe-west9",
            "me-west1",
            "northamerica-northeast1",
            "northamerica-northeast2",
            "southamerica-west1",
            "us-east5",
            "us-south1",
            "us-west2",
            "us-west3",
            "us-west4",
            "us-west4"
        ]
        try:
            regions = subprocess.run(
                "gcloud compute regions list --format=\"json\"",
                check=True,
                shell=True,
                capture_output=True,
                timeout=300
            ).stdout.decode()
            regions_outp_obj = json.loads(regions)
            result = [r["name"] for r in regions_outp_obj]
            return result
        except subprocess.CalledProcessError as exception:
            logging.error("Failed to get the regions dynamically; using defaults.")
            return default
        return default

CloudProvider.register(CloudProviderGCP)
