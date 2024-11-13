from hparams.localconfig import LocalConfig
import io
from contextlib import redirect_stderr
import argparse
import os
import gcsfs
import time


class HParams(LocalConfig):
    _loaded_hparams_objects = {}

    def __init__(self,
                 project_path,
                 hparams_filename="hparams",
                 gcs_backup_project=None,
                 gcs_backup_bucket=None,
                 name="hparams",
                 global_rank=0,
                 timeout=20,
                 ):
        if name in HParams._loaded_hparams_objects.keys():
            raise ValueError(f"hparams {name} is being loaded a second time")

        # params_to_override = HParams.override_params()

        super(HParams, self).__init__()

        self.read(os.path.join(project_path, f"{hparams_filename}.cfg"))

        if gcs_backup_project is not None:
            if gcs_backup_bucket is None:
                raise ValueError(f"GCS bucket must be provided to conduct gcs backup!")

            if not gcs_backup_bucket.startswith('gs://'):
                gcs_backup_bucket = 'gs://' + gcs_backup_bucket

            gcs_fs = gcsfs.GCSFileSystem(project=gcs_backup_project)
            gcs_backup_bucket = os.path.join(gcs_backup_bucket, self.run.name)

        else:
            gcs_fs = None

        # self.update(params_to_override)

        logdir = os.path.join(project_path, 'logs', self.run.name)
        logfile = os.path.join(logdir, 'hparams.cfg')
        sentinel_file = os.path.join(logdir, '.hparams_file_is_written')

        if os.path.isdir(logdir) and os.path.isfile(logfile) and os.path.isfile(sentinel_file):
            # If logfile is found, assume we are resuming as old run, so use archived hparams file
            super(HParams, self).__init__()
            self.read(logfile)
            # self.update(params_to_override)
            print('Found existing {}! Resuming run using primary parameters!'.format(logfile))
        else:
            if global_rank == 0:
                os.makedirs(logdir, exist_ok=True)
                self.save_config(logfile)
                with open(sentinal_file, 'w') as f:
                    f.write('okay')
                print('No existing config found. New run config file saved in {}'.format(logfile))
            else:
                start_time = time.time()
                while not os.path.isfile(sentinal_file):
                    if time.time() - start_time > timeout:
                        raise TimeoutError(f"Rank {global_rank} timed out waiting for {logfile} after {timeout}s")
                    time.sleep(0.1)

                super(Hparams, self).__init__()
                self.read(logfile)
                print(f'Rank {global_rank} loaded new config from {logfile}')

        if gcs_fs is not None and global_rank == 0:
            gcs_path = os.path.join(gcs_backup_bucket, os.path.basename(logfile))
            print(f'Backing up hparams file to {gcs_path}')
            gcs_fs.put(lpath=logfile, rpath=gcs_path)

        self.add_to_global_collections(name)

    def add_to_global_collections(self, name):
        HParams._loaded_hparams_objects[name] = self

    @staticmethod
    def get_hparams_by_name(name):
        return HParams._loaded_hparams_objects[name]

    @staticmethod
    def override_params():
        try:
            f = io.StringIO()
            with redirect_stderr(f):
                parser = argparse.ArgumentParser()
                parser.add_argument('override_params', nargs='+')
                args = parser.parse_args()

            params = args.override_params
        except:
            params = None
        return params
