import os
import uuid

from mcdreforged.api.all import *
from typing import List, Union, Dict, Optional, TYPE_CHECKING

from ruamel import yaml as _yaml
import json
from urllib.parse import quote

from multi_search.utils import named_thread


if TYPE_CHECKING:
    from multi_search.multi_search import MultiSearch


JSON = 'json'
YAML = 'yaml'


class SearchSchemeMetadata(Serializable):
    name: str = ''
    enabled: bool = False
    permission: int = 0
    default_broadcast: bool = False
    command_prefix: str = ''
    url: Dict[str, str] = {
        'default': "{keyword}"
    }


class Scheme:
    META_FILE_NAME = '.ms_scheme.meta.yml'
    LANG_FOLDER_NAME = 'lang'
    LANG_FILE_SUFFIXES = {JSON: '.json', YAML: ['.yml', '.yaml']}

    yaml = _yaml.YAML(typ='rt')
    yaml.width = 1048576
    yaml.indent(2, 2, 2)
    yaml.allow_unicode = True

    def __init__(self, multi_search: "MultiSearch", name: str):
        self.name = name
        self.__inst = multi_search
        self.__cached_scheme: SearchSchemeMetadata = self.load_meta()

    @property
    def dir_path(self):
        return self.__inst.get_data_folder(self.name)

    @property
    def scheme_meta_path(self):
        return os.path.join(self.dir_path, self.META_FILE_NAME)

    @property
    def lang_path(self):
        return os.path.join(self.dir_path, self.LANG_FOLDER_NAME)

    @property
    def enabled(self):
        return self.__cached_scheme.enabled

    @property
    def prefix(self):
        return self.__cached_scheme.command_prefix

    def reload(self):
        self.__cached_scheme = self.load_meta()

    @classmethod
    def get_locale_from_filename(cls, filename: str):
        for typ, suffixes in cls.LANG_FILE_SUFFIXES.items():
            for suffix in suffixes:
                if filename.endswith(suffix):
                    return typ, filename[:-len(suffix)]
        return None, None

    def create_default_lang(self):
        if os.path.isfile(self.lang_path):
            os.remove(self.lang_path)
        if not os.path.isdir(self.lang_path):
            os.makedirs(self.lang_path)
        with self.__inst.server.open_bundled_file('sample_language.yml') as f:
            default = f.read()
        for locale in ['en_us', 'zh_cn']:
            path = os.path.join(self.lang_path, f'{locale}.yml')
            with open(path, 'wb') as f:
                f.write(default)

    def register_translation(self):
        if not os.path.isdir(self.lang_path):
            return
        for lf in os.listdir(self.lang_path):
            typ, lang = self.get_locale_from_filename(lf)
            path = os.path.join(self.lang_path, lf)
            if lang is None:
                self.__inst.debug(f'Ignored language file {path}')
                continue
            with open(path, encoding='utf8') as f:
                if typ == JSON:
                    data = json.load(f)
                else:
                    data = self.yaml.load(f)
            self.__inst.server.register_translation(lang, {self.__inst.server.get_self_metadata().id: {self.name: data}})
            self.__inst.server.logger.info(f'Registered language {lang} for scheme {self.name}')

    def save_meta(self, meta: Optional[SearchSchemeMetadata] = None):
        if meta is None:
            meta = self.__cached_scheme
        with open(self.scheme_meta_path, 'w', encoding='utf8') as f:
            self.yaml.dump(meta.serialize(), f)

    def load_meta(self):
        def run():
            def save_default():
                default_meta = SearchSchemeMetadata.get_default()
                self.save_meta(meta=default_meta)
                return default_meta

            if not os.path.isfile(self.scheme_meta_path):
                return save_default()
            try:
                with open(self.scheme_meta_path, encoding='utf8') as f:
                    meta = SearchSchemeMetadata.deserialize(self.yaml.load(f))
                if meta.name != self.name:
                    meta.name = self.name
                self.save_meta(meta)
                return meta
            except (KeyError, ValueError, _yaml.YAMLError):
                return save_default()
        data = run()
        self.__inst.server.logger.info(f'Loaded scheme meta: {self.name}')
        return data

    def rtr(self, translation_key: str, *args, _rtr_prefix: Optional[str] = None, **kwargs) -> RTextMCDRTranslation:
        _rtr_prefix = _rtr_prefix or f"{self.__inst.server.get_self_metadata().id}.{self.name}."
        if not translation_key.startswith(_rtr_prefix):
            translation_key = f"{_rtr_prefix}{translation_key}"
        return self.__inst.server.rtr(translation_key, *args, **kwargs)

    @named_thread
    def search(self, source: CommandSource, keyword: str, is_broadcast: bool = False):
        for id_, url in self.__cached_scheme.url.items():
            text = ('[' + self.rtr(f'id.{id_}').set_styles(RStyle.bold) + '] ' + self.rtr(
                'search.text', keyword=keyword
            )).h(
                self.rtr('search.hover')
            ).c(RAction.open_url, url.format(keyword=quote(keyword)))
            if is_broadcast:
                self.__inst.server.say(text)
            else:
                source.reply(text)

    def register(self):
        meta = self.__cached_scheme
        kw_node = 'keyword'
        if meta.enabled:
            self.register_translation()
            if not meta.default_broadcast:
                node = Literal(meta.command_prefix).requires(lambda src: src.has_permission(meta.permission)).runs(
                    lambda src: src.reply(self.rtr('help.detailed'))
                ).then(
                    Literal('-a').then(
                        GreedyText(kw_node).runs(lambda src, ctx: self.search(src, ctx[kw_node], is_broadcast=True))
                    )
                ).then(
                    GreedyText(kw_node).runs(lambda src, ctx: self.search(src, ctx[kw_node]))
                )
            else:
                node = Literal(meta.command_prefix).requires(lambda src: src.has_permission(meta.permission)).runs(
                    lambda src: src.reply(self.rtr('help.detailed'))
                ).then(
                    Literal('-s').then(
                        GreedyText(kw_node).runs(lambda src, ctx: self.search(src, ctx[kw_node]))
                    )
                ).then(
                    GreedyText(kw_node).runs(lambda src, ctx: self.search(src, ctx[kw_node], is_broadcast=True))
                )
            self.__inst.server.register_command(node)
            self.__inst.server.register_help_message(meta.command_prefix, self.rtr('help.mcdr'))
