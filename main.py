import json
import os
import time
import requests
from datetime import datetime


class Config:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
    }
    immich_headers = {
        "Accept": "application/json",
    }
    clienttype = None
    bdstoken = None
    need_thumbnail = None
    need_filter_hidden = None
    need_amount = None
    need_member = None
    retry_times = 3
    request_timeout = 30
    immich_key = None

    def load_config(self):
        with open("config.json", "r", encoding="utf-8") as f:
            json_data = json.load(f)
            self.headers["Cookie"] = json_data["Cookie"]
            self.clienttype = json_data["clienttype"]
            self.bdstoken = json_data["bdstoken"]
            self.need_thumbnail = json_data["need_thumbnail"]
            self.need_filter_hidden = json_data["need_filter_hidden"]
            self.need_amount = json_data["need_amount"]
            self.need_member = json_data["need_member"]
            self.immich_key = json_data["immich_key"]
            self.immich_headers["x-api-key"] = self.immich_key


class Out:
    out_path = "./out"
    out_album_dir_path = f"{out_path}/album"
    out_file_dir_path = f"{out_path}/file"
    out_download_dir_path = f"{out_path}/download"
    out_albums_path = f"{out_path}/albums.json"
    out_files_path = f"{out_path}/files.json"
    out_success_path = f"{out_path}/success.json"
    out_failure_path = f"{out_path}/failure.json"
    successes = None

    def make_dirs(self):
        os.makedirs(self.out_path, exist_ok=True)
        os.makedirs(self.out_album_dir_path, exist_ok=True)
        os.makedirs(self.out_file_dir_path, exist_ok=True)
        os.makedirs(self.out_download_dir_path, exist_ok=True)

    def clear_album_dir(self):
        for it in os.listdir(self.out_album_dir_path):
            path = os.path.join(self.out_album_dir_path, it)
            if os.path.isfile(path):
                os.remove(path)

    def clear_file_dir(self):
        for it in os.listdir(self.out_file_dir_path):
            path = os.path.join(self.out_file_dir_path, it)
            if os.path.isfile(path):
                os.remove(path)

    def clear_download_dir(self):
        for it in os.listdir(self.out_download_dir_path):
            path = os.path.join(self.out_download_dir_path, it)
            if os.path.isfile(path):
                os.remove(path)

    def add_success(self, success):
        successes = self.get_successes()

        successes.add(success)

        with open(self.out_success_path, "w", encoding="utf-8") as f:
            json.dump(list(successes), f, ensure_ascii=False, indent=4)

    def add_failure(self, failure):
        failures = list()

        if os.path.exists(self.out_failure_path):
            with open(self.out_failure_path, "r", encoding="utf-8") as f:
                failures = json.load(f)

        failures.append(failure)

        with open(self.out_failure_path, "w", encoding="utf-8") as f:
            json.dump(failures, f, ensure_ascii=False, indent=4)

    def save_album_list(self, items):
        for it in items:
            path = f"{self.out_album_dir_path}/{it["album_id"]}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(it, f, ensure_ascii=False, indent=4)

    def save_file_list(self, items):
        for it in items:
            path = f"{self.out_file_dir_path}/{it["album_id"]}_{it["fsid"]}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(it, f, ensure_ascii=False, indent=4)

    def get_albums(self):
        albums = list()

        if os.path.exists(self.out_albums_path):
            with open(self.out_albums_path, "r", encoding="utf-8") as f:
                albums = json.load(f)

        return albums

    def get_files(self):
        files = list()

        if os.path.exists(self.out_files_path):
            with open(self.out_files_path, "r", encoding="utf-8") as f:
                files = json.load(f)

        return files

    def get_successes(self):
        if self.successes == None:
            self.successes = set()

            if os.path.exists(self.out_success_path):
                with open(self.out_success_path, "r", encoding="utf-8") as f:
                    self.successes = set(json.load(f))

        return self.successes


class Requester:
    retry_times = 3
    tried_times = 0

    def request(self, try_fn, catch_fn):
        self.tried_times = 0

        while True:
            try:
                if self.tried_times >= self.retry_times:
                    catch_fn()
                    return

                self.tried_times += 1
                result = try_fn()
                return result

            except Exception as e:
                print(f"请求失败, {e}, 重试 {self.tried_times}/{self.retry_times} ...")
                time.sleep(5)


class AlbumWalker:
    global config
    global out

    url = None
    cursor = None
    finished = False
    walked_i = 0
    requester = Requester()

    def walk(self):
        while not self.finished:
            self.url = f"https://photo.baidu.com/youai/album/v1/list?clienttype={config.clienttype}&bdstoken={config.bdstoken}&limit=30&need_amount=1&need_member=1&field=mtime"

            if self.cursor:
                self.url = f"{self.url}&cursor={self.cursor}"

            self.walked_i += 1

            def try_fn():
                print(f"Walking album list {self.walked_i}")
                response = requests.get(
                    self.url, headers=config.headers, timeout=config.request_timeout
                )
                response.raise_for_status()

                response_json = response.json()
                items = response_json.get("list", [])
                self.cursor = response_json.get("cursor")

                if items:
                    out.save_album_list(items)

                if not items:
                    self.finished = True

                if not self.cursor:
                    self.finished = True

            def catch_fn():
                out.add_failure(
                    {
                        "type": "album_list",
                        "walked_i": self.walked_i,
                        "url": self.url,
                        "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
                    }
                )
                self.finished = True

            self.requester.request(try_fn, catch_fn)

    def gen(self):
        albums = list()

        for it in os.listdir(out.out_album_dir_path):
            with open(f"{out.out_album_dir_path}/{it}", "r", encoding="utf-8") as f:
                album_data = json.load(f)
                album = {
                    "id": album_data["album_id"],
                    "title": album_data["title"],
                }
                albums.append(album)

        with open(f"{out.out_albums_path}", "w", encoding="utf-8") as f:
            json.dump(albums, f, ensure_ascii=False, indent=4)


class FileWalker:
    global config
    global out

    url = None
    formdata = None
    cursor = None
    finished = False
    walked_i = 0
    requester = Requester()

    def walk(self):
        albums = out.get_albums()
        for it in albums:
            self.url = None
            self.formdata = None
            self.cursor = None
            self.finished = False
            self.walk_album(it["id"])

    def walk_album(self, album):
        while not self.finished:
            self.url = f"https://photo.baidu.com/youai/album/v1/listfile?clienttype={config.clienttype}&bdstoken={config.bdstoken}"
            self.formdata = {
                "cursor": "",
                "album_id": album,
                "need_amount": "1",
                "limit": "100",
                "passwd": "",
            }

            if self.cursor:
                self.formdata["cursor"] = self.cursor

            self.walked_i += 1

            def try_fn():
                print(f"Walking file list {self.walked_i}")
                response = requests.post(
                    self.url,
                    headers=config.headers,
                    data=self.formdata,
                    timeout=config.request_timeout,
                )
                response.raise_for_status()

                response_json = response.json()
                items = response_json.get("list", [])
                self.cursor = response_json.get("cursor")

                if items:
                    out.save_file_list(items)

                if not items:
                    self.finished = True

                if not self.cursor:
                    self.finished = True

            def catch_fn():
                out.add_failure(
                    {
                        "type": "file_list",
                        "walked_i": self.walked_i,
                        "url": self.url,
                        "formdata": self.formdata,
                        "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
                    }
                )
                self.finished = True

            self.requester.request(try_fn, catch_fn)

    def gen(self):
        albums = out.get_albums()
        albums_map = dict()
        for it in albums:
            albums_map[it["id"]] = it
        files = list()

        for it in os.listdir(out.out_file_dir_path):
            with open(f"{out.out_file_dir_path}/{it}", "r", encoding="utf-8") as f:
                file_data = json.load(f)
                file = {
                    "id": f"{file_data["album_id"]}_{file_data["fsid"]}",
                    "fsid": file_data["fsid"],
                    "album_id": file_data["album_id"],
                    "album_title": albums_map[file_data["album_id"]]["title"],
                    "filename": file_data["path"][12:],
                    "dlink": file_data["dlink"],
                    "ctime": file_data["ctime"],
                    "mtime": file_data["mtime"],
                }
                files.append(file)

        with open(f"{out.out_files_path}", "w", encoding="utf-8") as f:
            json.dump(files, f, ensure_ascii=False, indent=4)


class Syncer:
    global config
    global out

    walked_i = 0
    requester = Requester()
    albums = list()
    albums_map = dict()

    def sync(self):
        files = out.get_files()
        files_len = len(files)

        for it in files:
            self.walked_i += 1

            print(f"Sync {self.walked_i}/{files_len}")

            successes = out.get_successes()
            if it["id"] in successes:
                print(f"Skip success {it["id"]}")
                continue

            if it["filename"].endswith(".livp"):
                print(f"Skip ext livp file {it["id"]}")
                continue

            print(f"Download file {it["id"]}")
            self.download(it)

            print(f"Upload asset {it["id"]}")
            asset_json = self.upload_asset(it)

            if not asset_json:
                print(f"Skip upload failure {it["id"]}")
                continue

            print(f"Add asset to album {it["id"]} {asset_json["id"]}")
            self.add_asset_to_album(it, asset_json)

            print(f"Remove file {it["id"]}")
            self.remove(it)

            print(f"Add success {it["id"]}")
            self.add_success(it)

    def download(self, file):
        def try_fn():
            url = file["dlink"]
            response = requests.get(
                url, headers=config.headers, timeout=config.request_timeout
            )
            response.raise_for_status()

            return response

        def catch_fn():
            out.add_failure(
                {
                    "type": "download_file",
                    "walked_i": self.walked_i,
                    "url": file["dlink"],
                    "id": file["id"],
                    "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
                }
            )

        response = self.requester.request(try_fn, catch_fn)

        if response == None:
            print(f"Skip download failure {file["id"]}")
            return

        save_path = f"{out.out_download_dir_path}/{file["filename"]}"
        with open(save_path, "wb") as f:
            f.write(response.content)

    def remove(self, file):
        save_path = f"{out.out_download_dir_path}/{file["filename"]}"

        if os.path.exists(save_path) and os.path.isfile(save_path):
            os.remove(save_path)

    def create_albums(self):
        url = "http://127.0.0.1:2283/api/albums"
        response = requests.get(
            url,
            headers=config.immich_headers,
            timeout=config.request_timeout,
        )
        response_json = response.json()

        for it in response_json:
            album = {
                "id": it["id"],
                "title": it["albumName"],
            }
            self.albums.append(album)
            self.albums_map[album["title"]] = album

        bd_albums = out.get_albums()

        for it in bd_albums:
            if it["title"] not in self.albums_map:
                print(f"Create album {it["title"]}")

                payload = json.dumps({"albumName": it["title"]})
                response = requests.post(
                    url,
                    headers=config.immich_headers
                    | {"Content-Type": "application/json"},
                    timeout=config.request_timeout,
                    data=payload,
                )
                response_json = response.json()

                album = {
                    "title": it["title"],
                    "id": it["id"],
                }
                self.albums.append(album)
                self.albums_map[album["title"]] = album

    def upload_asset(self, file):
        def try_fn():
            url = "http://127.0.0.1:2283/api/assets"
            save_path = f"{out.out_download_dir_path}/{file["filename"]}"
            stats = os.stat(save_path)
            payload = {
                "deviceAssetId": f"{file["filename"]}-{stats.st_mtime}",
                "deviceId": "python",
                "fileCreatedAt": datetime.fromtimestamp(file["ctime"]),
                "fileModifiedAt": datetime.fromtimestamp(file["mtime"]),
                "isFavorite": "false",
            }
            files = {"assetData": open(save_path, "rb")}

            response = requests.post(
                url,
                headers=config.immich_headers,
                timeout=config.request_timeout,
                data=payload,
                files=files,
            )
            response.raise_for_status()
            response_json = response.json()

            return response_json

        def catch_fn():
            out.add_failure(
                {
                    "type": "upload_asset",
                    "walked_i": self.walked_i,
                    "id": file["id"],
                    "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
                }
            )

        response_json = self.requester.request(try_fn, catch_fn)
        return response_json

    def add_asset_to_album(self, file, asset_json):
        def try_fn():
            album_title = file["album_title"]
            album_id = self.albums_map[album_title]["id"]

            url = f"http://127.0.0.1:2283/api/albums/{album_id}/assets"
            payload = json.dumps({"ids": [asset_json["id"]]})

            response = requests.put(
                url,
                headers=config.immich_headers | {"Content-Type": "application/json"},
                timeout=config.request_timeout,
                data=payload,
            )
            response.raise_for_status()

        def catch_fn():
            out.add_failure(
                {
                    "type": "add_asset_to_album",
                    "walked_i": self.walked_i,
                    "id": file["id"],
                    "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
                }
            )

        self.requester.request(try_fn, catch_fn)

    def add_success(self, file):
        out.add_success(file["id"])


config = Config()
config.load_config()
out = Out()
out.make_dirs()
out.clear_album_dir()
out.clear_file_dir()
out.clear_download_dir()
album_walker = AlbumWalker()
album_walker.walk()
album_walker.gen()
file_walker = FileWalker()
file_walker.walk()
file_walker.gen()
syncer = Syncer()
syncer.create_albums()
syncer.sync()
