from __future__ import annotations

import re
import warnings
from glob import glob
from pathlib import Path
from typing import Union, Iterable

_rDashedWord = r'(\w|-)+'

_known_oids = {'iso': None}

# _known_types = {"BOOLEAN", "INTEGER","BIT STRING","OCTET STRING","DATE","DATE","TIME-OF-DAY","DATE-TIME	"}
_known_types = {'INTEGER': None, 'OCTET STRING': None,"OBJECT IDENTIFIER":None}
_types_def_keywords = ("SEQUENCE", "OF", "SIZE", "FROM")


def partition(s, indices):
    return [s[i:j] for i, j in zip(indices, indices[1:] + [None])]


def s_strip(s):
    """ strip '\n \t' from given string"""
    return s.strip(' \n\t')


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
        self.name = re.compile(_rDashedWord).match(text).group()
        self.module = module  # parent module
        self.dependencies: dict[str, MibIdr] = {}
        self.mibCollector = module.mibCollector
        self.text = text

        self.mibCollector[self.name] = self


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
        m = re.search("(?<=SYNTAX)(.|\n)*?(?=ACCESS)", text)
        if m:
            # SYNTAX
            # typeName = s_strip(re.sub(r"\(.*\)", '', _remove_type_keywords(m.group())))
            # self.module.resolve_type(typeName)
            typeName = MibType.get_typeName(m.group())
            self.module.resolve_type(typeName)
        m = re.search("(?<=INDEX)(.|\n)*?(?=::=)", text)
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
                self.dependencies[dep] = self.mibCollector[dep]


class MibModule:
    """
     a module that holds information about mib file.

     not all text directly parsed to prevent loading of unnecessary oids and imports.
     parsing is taking place only by calling 'resolve_oid'. that will parse unparsed text left
     to resolve oid and then will clear relevant text.
     """

    def __init__(self, mibCollector, path):
        self.path = Path(path).resolve()
        with open(path) as f:
            text = f.read()
        self._i_md_start = re.compile(_rDashedWord + r' .*DEFINITIONS\s*::=\sBEGIN', re.M).search(text)
        self.name = re.compile(_rDashedWord, re.M).search(text, self._i_md_start.start()).group()
        self.mibCollector = mibCollector  # parent mibParser
        self.unparsedText = text

        self.imports: dict[str, MibModule] = {}
        self._parse_imports()

        self.requiredIdr: dict[str, Union[MibObjectID, MibType]] = {}
        self.requiredModules: dict[str, MibModule] = {}

    def _parse_imports(self):
        text = self.unparsedText
        st2 = re.compile('IMPORTS', re.M).search(text, self._i_md_start.end())
        if not st2:
            return
        st3 = re.compile(';', re.M).search(text, st2.end())
        imports_text = text[st2.end():st3.start()].strip('\t \n;')
        indexs = [match.end() for match in re.finditer(r'FROM\s+' + _rDashedWord, imports_text, re.M)]
        indexs.insert(0, 0)
        indexs.pop()
        for imp in partition(imports_text, indexs):
            oids, module = imp.split("FROM")
            module = s_strip(module)
            for oid in oids.split(','):
                oid = s_strip(oid)
                self.imports[oid] = module

    def resolve_oidName(self, oidName):
        return self.resolve_identifier(oidName, MibObjectID)

    def resolve_type(self, typeName):
        return self.resolve_identifier(typeName, MibType)

    def resolve_identifier(self, idrName, _IdrClass=None):
        if idrName in self.mibCollector:
            return
            # first resolve modules if required
        if idrName in self.imports:
            moduleName = self.imports[idrName]
            if moduleName not in self.requiredModules:
                self.resolve_module(moduleName)
            self.requiredModules[moduleName].resolve_identifier(idrName)
            return

        if not _IdrClass:
            if idrName[0].isupper():
                # this is type
                _IdrClass = MibType
            else:
                # this is oid
                _IdrClass = MibObjectID

        reg = re.compile(idrName + _IdrClass.def_reg)

        idr_m = reg.search(self.unparsedText)
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
        module = MibModule(self.mibCollector, _path)
        self.requiredModules[moduleName] = module
        return module


class MibParser:
    """
     receives a dict of object identifiers(oids), and build a mib which includes all their definitions and their dependencies.
     collects oids.

     at the end generate a custom module.

     identifiers with starting with lowercase letter referred as oid-name and capital letter as type
     """

    def __init__(self, identifiers: dict[str, str] = None, mainModuleName='my-mib'):
        if identifiers is None:
            identifiers = {}
        self.mainModuleName = mainModuleName
        self.identifiers: dict[str, MibObjectID] = {**_known_oids, **_known_types}
        self.modules: dict[str, MibModule] = {}
        self.require_identifier(identifiers)
        # self.types: dict[str, MibType] = {**_known_types}

    def require_identifier(self, idrs: dict[str, str]):
        """ requiring recursively an identifier (oid(lowercase first letter) or type(capital first letter)) """
        for idr, path in idrs.items():
            if path not in self.modules:
                self.modules[path] = MibModule(self, path)
            self.modules[path].resolve_identifier(idr)

    def eject_mib(self):
        mib_text = f'{self.mainModuleName} DEFINITIONS ::= BEGIN\n\n\n'
        for oid in self.identifiers.values():
            if oid:
                mib_text += oid.text + '\n\n'
        mib_text += '\n\n\nEND'
        return mib_text

    def __contains__(self, key):
        return key in self.identifiers

    def __getitem__(self, key):
        return self.identifiers[key]

    def __setitem__(self, key, value):
        self.identifiers[key] = value


def test():
    mibs_folder = Path(__file__).parent / "tests"

    # mapping between object names and mib files
    objectNames = {
        # "TimeTicks": f"{mibs_folder}/RFC1213-MIB.my",        # required items can also be types
        # "sysObjectID": f"{mibs_folder}/RFC1213-MIB.my",
        "frxT1OutOctets": f"{mibs_folder}/CISCO-90-MIB-V1SMI.my",
        # "dot1xPaeSystemAuthControl": f"{mibs_folder}/IEEE8021-PAE-MIB-V1SMI.my",
    }
    mibCollector = MibParser(objectNames)

    mib_text = mibCollector.eject_mib()
    with open('./tests/my-mib.my', 'w') as f:
        f.write(mib_text)


if __name__ == "__main__":
    test()
