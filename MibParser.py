from __future__ import annotations

import os
import re
import warnings
from glob import glob
from pathlib import Path
from typing import Union, Iterable, Optional

from Region import Region

# _rDWord = r'(\w|-)+'  # dashed word
_rDWord = r'[\w-]+'  # dashed word

_known_oids = {'iso': None}

# _known_types = {"BOOLEAN", "INTEGER","BIT STRING","OCTET STRING","DATE","DATE","TIME-OF-DAY","DATE-TIME	"}
_known_types = {'INTEGER': None, 'OCTET STRING': None, "OBJECT IDENTIFIER": None}
_types_def_keywords = ("SEQUENCE", "OF", "SIZE", "FROM")

pathType = Union[str, bytes, os.PathLike]


def partition(s, indices):
    return [s[i:j] for i, j in zip(indices, indices[1:] + [None])]


def s_strip(s: str, chars=' \n\t') -> str:
    """ strip '\n \t' from given string"""
    return s.strip(chars)


def ls_strip(l: list[str], chars=' \n\t') -> list[str]:
    return [s_strip(s, chars) for s in l]


def remove_strs(s: str, strs: Iterable[str]):
    for rm in strs:
        s = s.replace(rm, '')
    return s


def _remove_type_keywords(s):
    return remove_strs(s, _types_def_keywords)


class MibIdr:
    """
     identifier. (oid definition or type definition).
     automatically registers as identifier in mibParser parent in initialization.
    """

    def __init__(self, module: MibModule, text):
        self.name = re.compile(_rDWord).match(text).group()
        self.module = module  # parent module
        self.dependencies: dict[str, MibIdr] = {}
        self.mibParser = module.mibParser
        self.text = text

        self.mibParser[self.name] = self


_type_extensions = ["ENUMERATED", "SEQUENCE", "SET", "CHOICE"]
_type_plicit = ["EXPLICIT", "IMPLICIT"]

_r_type_extensions = re.compile(f"({r'|'.join(_type_extensions)})" + r'\s*\{(.|\n)*?\}')
_r_not_type_extensions = re.compile(r'(?<=INTEGER)\s*\{(.|\n)*?\}')


class MibType(MibIdr):
    """
    object that holds information about oid-type. immediately parsed.
    """
    def_reg = r'\s+::=(.|\n)*?(?=(\w|-)+\s*::=|END|(\w|-)+\s*OBJECT-TYPE)'

    @staticmethod
    def get_typeName(text):
        """ remove all the constraint and keywords and leave only type name """
        clean = s_strip(re.sub(r"\(.*\)", '', _remove_type_keywords(text)))
        clean = _r_not_type_extensions.sub('', clean)
        return clean

    def __init__(self, module: MibModule, text):
        MibIdr.__init__(self, module, text)

        m = _r_type_extensions.search(text)
        if m:
            self.EXTENSIONS = m.group()
            # should include extensions as well:
            exts = self.EXTENSIONS[re.search(r'\w+', self.EXTENSIONS).end():].strip(' \n\t{}')
            exts = exts.split(',')
            for ext in exts:
                oid, type = ext.split()
                self.module.resolve_oidName(oid)
                self.module.resolve_type(self.get_typeName(type))
            pass

        m = re.search(r'(?<=::=)(.|\n)*?\[.*?\]', text)
        if m:
            self.TAG = s_strip(m.group())
        m = re.compile(r'|'.join(_type_plicit)).search(text)
        if m:
            self.PLICIT = s_strip(m.group())


class MibObjectID(MibIdr):
    """
    object that holds information about oid. immediately parsed.
    """

    # def_reg = r'\s+OBJECT([^:\{\}]|\{[^:]+\})+::=\s*\{([^\}]+)\}'  # scapy-version
    # def_reg = r'\s*OBJECT-TYPE(.|\n)*?::=\s*\{.*?\}'  # my-version
    def_reg = r'\s*OBJECT(-TYPE| IDENTIFIER)(.|\n)*?::=\s*\{.*?\}'  # my-version2

    # _OID_KEYWORDS = ["SYNTAX", "ACCESS", "STATUS", "DESCRIPTION", "REFERENCE", "INDEX"]

    def __init__(self, module: MibModule, text):
        MibIdr.__init__(self, module, text)

        self.SYNTAX = ...
        self.ACCESS = ...
        self.STATUS = ...
        self.DESCRIPTION = ...
        self.REFERENCE = ...
        self.INDEX = ...

        # extract dependent types
        m = re.search("(?<=SYNTAX)(.|\n)*?(?=(MAX-)?ACCESS)", text)
        if m:
            # SYNTAX
            typeName = MibType.get_typeName(m.group())
            self.module.resolve_type(typeName)
        m = re.search('(?<=INDEX)(.|\n)*?(?=::=)', text)
        if m:
            # INDEX
            oids = [s_strip(oid) for oid in _remove_type_keywords(m.group()).strip('\n \t{}').split(',')]
            for oid in oids:
                self.module.resolve_oidName(oid)

        en = re.search(r'::=', text)
        deps_m = re.compile(r'\{(.|\n)+?}').search(text, en.end())
        deps = deps_m.group().strip('{}').split()
        for dep in deps:
            if re.match(r'^(?!\d)(\w|-)+$', dep):
                self.module.resolve_oidName(dep)
                self.dependencies[dep] = self.mibParser[dep]


class MibRegions:
    """ each region contains regex match referring to original text region(to save time)"""

    def __init__(self, text):
        t = Optional[Region]
        self.START: t = None
        self.EXPORTS: t = None
        self.IMPORTS: t = None
        self.DEFS: t = None

        self._delimit_regions(text)

    def _delimit_regions(self, text):
        regions_regs = {
            # 'START': r'(\w|-)+.*DEFINITIONS\s*::=\sBEGIN',
            'START': r'(\w|-)+(.|\n)*DEFINITIONS\s*::=\s+BEGIN',
            "EXPORTS": r'EXPORTS(.|\n)*?;',
            "IMPORTS": r'IMPORTS(.|\n)*?;',
            "DEFS": '(.|\n)*(=?END)'
        }

        text = "".join(re.split(r'--.*(\r|\n)', text))

        i = 0
        for regionName, reg in regions_regs.items():
            m = Region(text, reg, i)
            setattr(self, regionName, m)
            if m:
                i = m.end()


class MibModule:
    """
     a module that holds information about mib file.

     not all text directly parsed to prevent loading of unnecessary oids and imports.
     parsing is taking place only by calling 'resolve_oid'. that will parse unparsed text left
     to resolve oid and then will clear relevant text.
     """

    def __init__(self, mibParser: MibParser, path):
        self.mibParser = mibParser  # parent mibParser
        self.path = Path(path).resolve()
        with open(path) as f:
            text = f.read()
        self.text = text
        self.regions = MibRegions(text)
        if not self.regions.START:
            raise Exception(f'unvalid syntax in module {self.path}')
        self.name = self.regions.START.search(_rDWord).group()
        if not self.mibParser.fast_load:
            print(f'parsing moudle {self.name}')

        # self.regions.DEFS.search('[\w]')
        # self._i_md_start = re.compile(_rDWord + r' .*DEFINITIONS\s*::=\sBEGIN', re.M).search(text)
        # self.name = re.compile(_rDWord, re.M).search(text, self._i_md_start.start()).group()

        # {idrName:mibPath which defines idrName}
        self.imported_idrs: dict[str, str] = {}
        self._parse_imports()

        # {idrName:MibModule which defines idrName}
        self.requiredModules: dict[str, MibModule] = {}

        # {idrName:idr definition text}
        self.defined_idrs: dict[str, str] = {}
        self._parse_all_definitions()
        # self.idrDefs: dict[str, Union[MibObjectID, MibType]] = {}

    def _parse_imports(self):
        """ make the module be aware what idrs are imported and from which module """
        # imports_text = re.search(r'(?<=IMPORTS)(.|\n)*?(?=;)', self.text).group()
        if not self.regions.IMPORTS: return
        m = self.regions.IMPORTS.narrow(r'(?<=IMPORTS)(.|\n)*?(?=;)')
        for imp in m.finditer(r'[\s\S]*?FROM\s+([\w-]+)'):
            idrs, module = imp.group().split('FROM')
            idrs = ls_strip(idrs.split(','))
            module = s_strip(module)
            for idr in idrs:
                self.imported_idrs[idr] = module

    def _parse_all_definitions(self):
        """ build dictionary of {idrName:definition-text} for faster search
         Note: expensive calculation"""
        defs = self.regions.DEFS.finditer(f'({_rDWord + MibObjectID.def_reg})|({_rDWord + MibType.def_reg})')
        for d in defs:
            m_idrName = d.search(r'[\w-]+')
            self.defined_idrs[m_idrName.group()] = d.group()

    def resolve_oidName(self, oidName):
        return self.resolve_identifier(oidName, MibObjectID)

    def resolve_type(self, typeName):
        return self.resolve_identifier(typeName, MibType)

    def resolve_identifier(self, idrName, _IdrClass=None):
        if idrName in self.mibParser:
            return
            # first resolve modules if required
        if idrName in self.imported_idrs:
            moduleName = self.imported_idrs[idrName]
            if moduleName not in self.requiredModules:
                self.resolve_module(moduleName)
            self.requiredModules[moduleName].resolve_identifier(idrName)
            return

        if not self.regions.DEFS:
            return

        if not _IdrClass:
            if idrName[0].isupper():
                # this is type
                _IdrClass = MibType
            else:
                # this is oid
                _IdrClass = MibObjectID

        # reg = re.compile(idrName + _IdrClass.def_reg)
        # idr_m_test = reg.search(self.text)

        idr_m = self.regions.DEFS.search(idrName + _IdrClass.def_reg)
        # if idr_m_test.group() != idr_m.group():
        #     raise Exception("error!")

        if not idr_m:
            warnings.warn(f'cant resolve identifier {idrName}')
            return
        idr_def_text = s_strip(idr_m.group())  # get idr definition text
        idr = _IdrClass(self, idr_def_text)
        return idr  # return reference for inner use

    def resolve_module(self, moduleName):
        path = Path(self.path).parent / moduleName
        try:
            _path = glob(str(path) + '.*')[0]
        except IndexError:
            warnings.warn(f"can't resolve module {moduleName} at path {path}")
            return
        module = MibModule(self.mibParser, _path)
        self.requiredModules[moduleName] = module
        return module


class MibParser:
    """
     receives a dict of object identifiers(oids), and build a mib which includes all their definitions and their dependencies.
     collects oids.

     at the end generate a custom module.

     identifiers starting with lowercase letter referred as oid-name and capital letter as type
     """

    mib_exteinsons = ('my', 'mib', 'txt')

    def __init__(self, mainModuleName='my-mib', idrs_dict: dict[str, str] = None, idrs_list: list[str] = None,
                 mibs_paths: Union[list[pathType], pathType] = None, fast_load: bool = True):
        """

        :param mainModuleName: the name of the module that will be generated using eject_mib() method
        :param idrs_dict: a dictionary of oid:mibPath pairs. for example {"sysObjectID":"./RFC1213-MIB.my"}
        :param idrs_list: a list of oids that will be resolve from mibs}
        :param mibs_paths: list of mibs that will be loaded and when oid doesn't resolve it will be looked at this
        :param fast_load: if set to true FAST LOADING algorithm will be chosen, else FAST SEARCHING algorithm will be chosen.
        if not given algorithm chosen automatically.
        """
        if mibs_paths is None:
            mibs_paths = []
        if type(mibs_paths) != list:
            mibs_paths = [mibs_paths]
        if idrs_list is None:
            idrs_list = []
        if idrs_dict is None:
            idrs_dict = {}

        self.fast_load = fast_load

        # idrs that shoud be included in the final generated mib file
        self.required_idrs = list(idrs_dict) + idrs_list
        # the name of the module that will be created
        self.mainModuleName = mainModuleName

        # already required,parsed identifiers. this dict will be filled at runtime
        self.parsed_identifiers: dict[str, MibObjectID] = {**_known_oids, **_known_types}

        # all required modules to parse required_idrs
        self.modules: dict[str, MibModule] = {}
        self.require_identifiers(idrs_dict)

        # load mibs needed to resolve idrs_list
        self.loaded_parsed_mibs: dict[str, MibModule] = {}
        self.loaded_text_mibs: dict[str, str] = {}
        self.load_mibs(mibs_paths)
        # self.loaded_mibs: dict[str, str] = {}

        # start the main logic of searching and resolving oids in the mibs
        self.require_identifier_list(idrs_list)

        print(f'Finished building {self.mainModuleName}')

    def _get_mib_from_identifier(self, idrName: str) -> str:
        """ search for specific identifier definition in a text mib file """
        # check if idrName already resolved
        if idrName in self.parsed_identifiers:
            return self.parsed_identifiers[idrName].module.name
        if self.fast_load:
            self._get_mib_from_identifier_fast_load(idrName)
        else:
            self._get_mib_from_identifier_fast_search(idrName)

    def _get_mib_from_identifier_fast_load(self, idrName: str):
        # resolve idrName from unparsed loaded mib files
        oid_c = re.compile(f'({idrName + MibObjectID.def_reg})|({idrName + MibType.def_reg})')
        if self.fast_load:
            print(f'searching oid {idrName}')
        for path, val in self.loaded_text_mibs.items():
            m = oid_c.search(val)
            if m:
                self.require_identifiers({idrName: path})

    def _get_mib_from_identifier_fast_search(self, idrName: str):
        for mibPath, mibModule in self.loaded_parsed_mibs.items():
            if idrName in mibModule.defined_idrs:
                mibModule.resolve_identifier(idrName)

    def require_identifier_list(self, idrs: list[str]):
        """ parse list of identifiers without mibPath then search what mib defines this ldr from loaded_mibs and
        return dict of {idr:mibPath} pairs
        fast load.
        """

        for idrName in idrs:
            self.require_identifiers({idrName: self._get_mib_from_identifier(idrName)})

    def require_identifiers(self, idrs: dict[str, str]):
        """ requiring recursively identifiers (oid(lowercase first letter) or type(capital first letter)) """
        for idr, path in idrs.items():
            if idr in self.parsed_identifiers:
                return
            if path not in self.modules:
                self.modules[path] = MibModule(self, path)
            self.modules[path].resolve_identifier(idr)

    def load_mibs_fast_load(self, mibFiles):
        """ fast loading algorithm but slower searching time
       choose this if you have a lot of mib files and small amount of oids"""
        for file in mibFiles:
            with open(file) as f:
                self.loaded_text_mibs[file] = f.read()

        # if idrName in self.parsed_identifiers:
        #     return self.parsed_identifiers[idrName].module.name
        #
        # for mibPath, mibModule in self.loaded_mibs.items():
        #     if idrName in mibModule.defined_idrs:
        #         mibModule.resolve_identifier(idrName)

    def load_mibs_fast_search(self, mibFiles):
        """ fast searching algorithm but slower loading time
        choose this if you have a lot of oids to search in small amount of mib files"""
        for file in mibFiles:
            # Note: MibModule(...) operation takes a lot of time for many files
            self.loaded_parsed_mibs[file] = MibModule(self, file)

    def load_mibs(self, paths: list[pathType]):
        """
        load mib text files into dict
        choosing best fastest to do so automatically.
         """
        mibFiles = []
        for reg in paths:
            mibFiles += glob(reg)

        # TODO: add smart automatically choosing algorithm
        # if len(self.required_idrs)>len(mibFiles):
        # self.fast_load = True

        if self.fast_load:
            print('using fast loading algorithm')
            self.load_mibs_fast_load(mibFiles)
        else:
            print('using fast searching algorithm')
            self.load_mibs_fast_search(mibFiles)

    def eject_mib(self, path=None):
        mib_text = f'{self.mainModuleName} DEFINITIONS ::= BEGIN\n\n\n'
        for oid in self.parsed_identifiers.values():
            if oid:
                mib_text += oid.text + '\n\n'
        mib_text += '\n\n\nEND'

        if path:
            p = f'{os.path.dirname(__file__)}/tests/{self.mainModuleName}.my'
            print(f'saving {self.mainModuleName} to {p}')
            with open(p, 'w') as f:
                f.write(mib_text)

        return mib_text

    def __contains__(self, key):
        return key in self.parsed_identifiers

    def __getitem__(self, key):
        return self.parsed_identifiers[key]

    def __setitem__(self, key, value):
        self.parsed_identifiers[key] = value


def test_dict():
    object_names_dirs = {
        "dot1xPaeSystemAuthControl": f"tests/IEEE8021-PAE-MIB-V1SMI.my",
    }
    mibParser = MibParser('test-dict-mib', idrs_dict=object_names_dirs)
    mibParser.eject_mib('path')


def test_list_with_loading():
    # mapping between object names and mib files

    object_names = [
        'TimeTicks',  # required items can also be types
        'frxT1OutOctets',
        'dot1xPaeSystemAuthControl',
        "frxH6EsTx"
    ]
    mibs_paths = [
        'tests/*'
    ]
    mibParser = MibParser('test-loading-mib', idrs_list=object_names, mibs_paths=mibs_paths)
    mibParser.eject_mib('./tests')


if __name__ == "__main__":
    import time

    start_time = time.time()

    test_dict()
    test_list_with_loading()

    print(f'execution time:{time.time() - start_time}')
