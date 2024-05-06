# generate from base common code
import string
from typing import Union, AnyStr, Optional
import ctypes
import datetime
import random
import collections
import io
import logging
import threading
import time
from typing.io import IO
import os
import re
import platform
import sys
def date_format(_date: Union[float, str] = None, fmt="%Y-%m-%d %H:%M",
                from_fmt="%Y-%m-%d %H:%M", day=False) -> str:
    """
    时间格式化
    :param day:
    :param _date: 输入时间
    :param fmt: 输出格式
    :param from_fmt: 输入字符时格式
    :return: 格式输出
    """
    if day:
        fmt = "%Y-%m-%d"
    if type(_date) == float:
        date_time = datetime.datetime.fromtimestamp(_date)
    elif type(_date) == str:
        date_time = datetime.datetime.strptime(_date, from_fmt)
    else:
        date_time = datetime.datetime.now()
    return date_time.strftime(fmt)
def random_str():
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(10))
def read_config(file=None, default_dict=None, apend_default=False):
    if not file:
        file = os.path.join(home_path(), f"config_py.ini")
    _mk_file_dir(file)
    if not os.path.exists(file) and default_dict is not None:
        write_config(default_dict, file)
        return None
    lines = read_file(file, True)
    ordered_dict = collections.OrderedDict()
    list_key = None
    for line in lines:
        split = line.split("#", 1)[0].split("=", 1)
        key = None if split[0] == "None" else int(split[0]) if split[0].isdigit() else split[0]
        if len(split) == 1:
            match = re.match("\[(.*)\]", key)
            if match:
                list_key = match.group(1)
                ordered_dict[list_key] = collections.OrderedDict()
        if len(split) >= 2:
            split_ = None if split[1] == "None" else int(split[1]) if split[1].isdigit() else split[1]
            if list_key:
                ordered_dict.get(list_key)[key] = split_
            else:
                ordered_dict[key] = split_
    if apend_default and default_dict:
        update = False
        for key in default_dict:
            if key not in ordered_dict:
                ordered_dict[key] = default_dict.get(key)
                update = True
        if update:
            write_config(ordered_dict, file)
    return ordered_dict
def _mk_file_dir(file):
    dirname = os.path.dirname(file)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)
def read_file(file, back_list=True):
    if not os.path.exists(file):
        return [] if back_list else ""
    with open(file, 'r', encoding="utf-8") as f:
        if back_list:
            text_list = f.readlines()
            for i in range(len(text_list)):
                text_list[i] = text_list[i].strip()
        else:
            text_list = "".join(f.readlines())
    return text_list
def write_config(sort_dict: dict, file=None):
    if not file:
        file = os.path.join(home_path(), f"config_py_{FileSys.split_path(sys.argv[0])[1]}.ini")
    lines = []
    for key in sort_dict:
        if type(sort_dict[key]) == dict or type(sort_dict[key]) == collections.OrderedDict:
            lines.append(f"[{key}]")
            for k in sort_dict[key]:
                lines.append(f"{k}={sort_dict[key][k]}")
        else:
            lines.append(f"{key}={sort_dict[key]}")
    write_file(lines, file=file)
def write_file(text_list, file="text.txt", append=False):
    _mk_file_dir(file)
    mode = 'a' if append else 'w'
    if type(text_list) == list:
        with open(file, mode, encoding="utf-8") as f:
            for line in text_list:
                f.write(line + "\n")
    if type(text_list) == str:
        with open(file, mode, encoding="utf-8") as f:
            f.writelines(text_list)
def home_path():
    return os.path.expanduser("~")
class FileSys:
    def __init__(self):
        self.name = "python_base"
        self.__path_num = 0

    def out_path(self, file, add_path="out_py"):
        self.__path_num += 1
        directory, name, ext = self.split_path(file)
        save_dir = os.path.join(directory, add_path, name)
        if not os.path.exists(save_dir) and self.__path_num == 1:
            os.makedirs(save_dir)
        save_file = os.path.join(save_dir, name + str(self.__path_num) + ext)
        return save_file

    def get_outfile(self, file, addition="new"):
        directory, name, ext = self.split_path(file)
        new_file = os.path.join(directory, name + "_" + addition + ext)
        return new_file

    @staticmethod
    def split_path(file):
        """
        split path to (directory, name, ext)
        :param file: (directory, name, ext)
        :return:
        """
        basename = os.path.basename(file)
        directory = os.path.dirname(file)
        ext = os.path.splitext(file)[-1]
        name = re.sub(ext, '', basename)
        return directory, name, ext
def split_path(file):
        """
        split path to (directory, name, ext)
        :param file: (directory, name, ext)
        :return:
        """
        basename = os.path.basename(file)
        directory = os.path.dirname(file)
        ext = os.path.splitext(file)[-1]
        name = re.sub(ext, '', basename)
        return directory, name, ext
def log(msg, file=None, console=True, fmt='%(asctime)s - %(levelname)s - %(message)s', flush_now=True):
    """日志打印"""
    handlers = logging.root.handlers
    if not any(h.get_name() == "base_log_handler" for h in handlers):
        # 已存在当前方法的handle
        for h in handlers:
            logging.root.removeHandler(h)
        if file:
            dirname = os.path.dirname(file)
            os.makedirs(dirname, exist_ok=True)
            file_handler = logging.FileHandler(file, mode='a', encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(fmt))
            file_handler.set_name("base_log_handler")
            logging.root.addHandler(file_handler)

        if console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(logging.Formatter(fmt))
            console_handler.set_name("base_log_handler")
            logging.root.addHandler(console_handler)
        logging.root.setLevel(logging.DEBUG)
        handlers = logging.root.handlers
    logging.info(msg)
    if flush_now:
        for h in handlers:
            h.flush()