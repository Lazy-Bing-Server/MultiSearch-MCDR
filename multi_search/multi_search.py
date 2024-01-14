import os

from mcdreforged.api.all import *
from multi_search.scheme import Scheme
from typing import Dict


class MultiSearch:
    DEBUG = True

    def __init__(self):
        self.server = ServerInterface.psi()
        self.__schemes: Dict[str, Scheme] = {}

    def get_data_folder(self, *path):
        base_dir = self.server.get_data_folder()
        if len(path) == 0:
            return base_dir
        target_dir = os.path.join(base_dir, *path)
        if os.path.isfile(target_dir):
            os.remove(target_dir)
        if not os.path.isdir(target_dir):
            os.makedirs(target_dir)
        return target_dir

    def load_schemes(self):
        for item in os.listdir(self.get_data_folder()):
            if os.path.isdir(os.path.join(self.get_data_folder(item))):
                self.__schemes[item] = Scheme(self, item)

    def debug(self, text: str):
        self.server.logger.debug(text, no_check=self.DEBUG)

    def list(self, source: CommandSource):
        for name, scheme in self.__schemes.items():
            symbol = '√' if scheme.enabled else 'x'
            source.reply(f'[§n{symbol}§r] {scheme.prefix} => {name}')

    def reload(self, source: CommandSource):
        source.reply('Reloaded')
        self.server.reload_plugin(self.server.get_self_metadata().id)

    def new(self, source: CommandSource, new_name: str):
        self.__schemes[new_name] = Scheme(self, new_name)
        self.__schemes[new_name].create_default_lang()
        source.reply(f'Scheme created: {new_name}, pls check meta and enable')

    def on_load(self):
        self.load_schemes()

        for name, scheme in self.__schemes.items():
            self.debug(f'enabled: {scheme.enabled}')
            scheme.register()

        _name = 'name'
        self.server.register_command(
            Literal('!!ms').requires(lambda src: src.has_permission(4)).then(
                Literal('list').runs(self.list)
            ).then(
                Literal('new').then(
                    QuotableText(_name).requires(
                        lambda src, ctx: ctx[_name] not in self.__schemes.keys()
                    ).runs(
                        lambda src, ctx: self.new(src, ctx[_name])
                    )
                )
            ).then(
                Literal('reload').runs(self.reload)
            )
        )
