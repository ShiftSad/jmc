from json import JSONDecodeError, dump, dumps, loads
from shutil import rmtree
from pathlib import Path
from typing import Any

from .header import parse_header, Header
from .lexer import Lexer
from .log import Logger
from .datapack import DataPack
from .exception import JMCBuildError


logger = Logger(__name__)
JMC_CERT_FILE_NAME = 'jmc.txt'


def compile(config: dict[str, str], debug: bool = False) -> None:
    """
    Compile the files and build the datapack

    :param config: Configuration dictionary
    :param debug: Whether to debug into log, defaults to False
    """
    logger.info("Configuration:\n"+dumps(config, indent=2))
    Header.clear()
    read_cert(config)
    read_header(config)
    logger.info("Parsing")
    lexer = Lexer(config)
    if debug:
        logger.info(f'Datapack :{lexer.datapack!r}')
    build(lexer.datapack, config)


def cert_config_to_string(cert_config: dict[str, str]) -> str:
    """
    Turns certificate configuration dictionary into a string for output

    :param cert_config: Certificate configuration dictionary
    :return: Converted string
    """
    return '\n'.join([f"{key}={value}" for key, value in cert_config.items()])


def string_to_cert_config(string: str) -> dict[str, str]:
    """
    Turns string into certificate configuration dictionary for further read

    :param string: String for convertion
    :return: Converted cert_config
    """
    cert_config = dict()
    for line in string.split('\n'):
        key, value = line.split('=')
        cert_config[key.strip()] = value.strip()
    return cert_config


def make_cert(cert_config: dict[str, str], path: Path) -> None:
    """
    Write certificate file

    :param cert_config: Certificate configuration
    :param path: Path to write `cert_config` to
    """
    path.parent.mkdir(parents=True, exist_ok=False)
    with path.open('w+') as file:
        file.write(cert_config_to_string(cert_config))


def get_cert() -> dict[str, str]:
    """
    Make a new Certificate configuration from current DataPack class info

    :return: Certificate configuration
    """
    return {
        "LOAD": DataPack.LOAD_NAME,
        "TICK": DataPack.TICK_NAME,
        "PRIVATE": DataPack.PRIVATE_NAME,
        "VAR": DataPack.VAR_NAME,
        "INT": DataPack.INT_NAME
    }


def read_header(config: dict[str, str]) -> bool:
    """
    Read the main header file

    :param config: JMC configuration
    :return: Whether the main header file was found
    """
    header = Header()
    header_file = Path(config["target"][:-len(".jmc")]+".hjmc")
    parent_target = Path(config["target"]).parent
    if header_file.is_file():
        header.add_file_read(header_file)
        logger.info("Header file found.")
        with header_file.open('r') as file:
            header_str = file.read()
        logger.info(f"Parsing {header_file}")
        parse_header(header_str, header_file.as_posix(), parent_target)
    else:
        logger.info("Header file not found.")

def read_cert(config: dict[str, str]):
    """
    Read Certificate(JMC.txt)

    :param config: JMC configuration
    :raises JMCBuildError: Can't find JMC.txt
    """
    namespace_folder = Path(config["output"])/'data'/config["namespace"]
    cert_file = namespace_folder/JMC_CERT_FILE_NAME
    old_cert_config = get_cert()
    if namespace_folder.is_dir():
        if not cert_file.is_file():
            raise JMCBuildError(
                f"{JMC_CERT_FILE_NAME} file not found in namespace folder.\n To prevent accidental overriding of your datapack please delete the namespace folder yourself.")

        with cert_file.open('r') as file:
            cert_str = file.read()
            try:
                cert_config = string_to_cert_config(cert_str)
            except ValueError:
                cert_config = dict()
            DataPack.LOAD_NAME = cert_config.get(
                "LOAD", old_cert_config["LOAD"])
            DataPack.TICK_NAME = cert_config.get(
                "TICK", old_cert_config["TICK"])
            DataPack.PRIVATE_NAME = cert_config.get(
                "PRIVATE", old_cert_config["PRIVATE"])
            DataPack.VAR_NAME = cert_config.get(
                "VAR", old_cert_config["VAR"])
            DataPack.INT_NAME = cert_config.get(
                "INT", old_cert_config["INT"])
            cert_config = get_cert()
        rmtree(namespace_folder.resolve().as_posix())
    else:
        cert_config = old_cert_config
    make_cert(cert_config, cert_file)


def read_func_tag(path: Path, config: dict[str, str]) -> dict[str, Any]:
    """
    Read minecraft function tag file

    :param path: Path to minecraft function tag file
    :param config: JMC configuration
    :raises JMCBuildError: MalformedJsonException
    :raises JMCBuildError: Can't find `values` key in json
    :return: Content of function tag file in dictionary
    """
    if path.is_file():
        with path.open('r') as file:
            content = file.read()
        try:
            json: dict[str, Any] = loads(content)
            json["values"] = [
                value for value in json["values"] if not value.startswith(config["namespace"]+':')]
        except JSONDecodeError:
            raise JMCBuildError(
                f"MalformedJsonException: Cannot parse {path.resolve().as_posix()}. Deleting the file to reset.")
        except KeyError:
            raise JMCBuildError(
                f'"values" key not found in {path.resolve().as_posix()}. Deleting the file to reset.')
    else:
        json = {"values": []}
    return json


def build(datapack: DataPack, config: dict[str, str]):
    """
    Build and write files for minecraft datapack

    :param datapack: DataPack object
    :param config: JMC configuration
    """
    logger.debug("Building")
    datapack.build()
    output_folder = Path(config["output"])
    namespace_folder = output_folder/'data'/config["namespace"]
    functions_tags_folder = output_folder/'data'/'minecraft'/'tags'/'functions'

    functions_tags_folder.mkdir(exist_ok=True, parents=True)
    load_tag = functions_tags_folder/'load.json'
    tick_tag = functions_tags_folder/'tick.json'

    load_json = read_func_tag(load_tag, config)
    tick_json = read_func_tag(tick_tag, config)

    load_json["values"].append(f'{config["namespace"]}:{DataPack.LOAD_NAME}')
    with load_tag.open('w+') as file:
        dump(load_json, file, indent=2)

    if DataPack.TICK_NAME in datapack.functions and datapack.functions[DataPack.TICK_NAME]:
        tick_json["values"].append(
            f'{config["namespace"]}:{DataPack.TICK_NAME}')
        with tick_tag.open('w+') as file:
            dump(tick_json, file, indent=2)

    for func_path, func in datapack.functions.items():
        path = namespace_folder/'functions'/(func_path+'.mcfunction')
        content = func.content
        if content:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w+') as file:
                file.write(func.content)

    for json_path, json in datapack.jsons.items():
        path = namespace_folder/(json_path+'.json')
        if json:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w+') as file:
                file.write(dumps(json, indent=2))

    with (output_folder/'pack.mcmeta').open('w+') as file:
        dump({
            "pack": {
                "pack_format": int(config["pack_format"]),
                "description": config["description"]
            }
        }, file, indent=2)
