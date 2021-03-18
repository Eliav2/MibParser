## Python MibParser

a simple mib parser. I did not like all the complicated parser out there, and which i encountered a lot of bugs, so I
wrote my own parser.

this is not general parser - the main usage of this parser:
collect and build a mib file from multiple mib files based on given oid-names. it will recursively collect all dependent
oids and types to a single mib file, in the same order as mentioned.

### Example:

let's say you want to build a mib for the oid sysObjectID which defined in RFC1213-MIB.my in the current directory. also
note that you have to include all dependent mib files in the same directory. so:

```python
from MibParser import MibParser

mibParser = MibParser(idrs_dict={"sysObjectID": "RFC1213-MIB.my"})
mib_text = mibParser.eject_mib()
with open('my-mib.my', 'w') as f:
    f.write(mib_text)
```

will output to my-mib.my this text:

```smi
my-mib DEFINITIONS ::= BEGIN


sysObjectID OBJECT-TYPE
              SYNTAX  OBJECT IDENTIFIER
              ACCESS  read-only
              STATUS  mandatory
                 DESCRIPTION
                      "The vendor's authoritative identification of the
                      network management subsystem contained in the
                      entity.  This value is allocated within the SMI
                      enterprises subtree (1.3.6.1.4.1) and provides an
                      easy and unambiguous means for determining `what
                      kind of box' is being managed.  For example, if
                      vendor `Flintstones, Inc.' was assigned the
                      subtree 1.3.6.1.4.1.4242, it could assign the
                      identifier 1.3.6.1.4.1.4242.1.1 to its `Fred
                      Router'."
              ::= { system 2 }

system       OBJECT IDENTIFIER ::= { mib-2 1 }

mib-2      OBJECT IDENTIFIER ::= { mgmt 1 }

mgmt          OBJECT IDENTIFIER ::= { internet 2 }

internet      OBJECT IDENTIFIER ::= { iso org(3) dod(6) 1 }




END
```

this independent mib file constructed from RFC1213-MIB.my(the direct dependent) and from RFC1155-SMI.my(second
dependent). you can see and run more complicated example by running directly MibParser.py.

if you don't know what is the mib defines an oid-name then you need to preload all possible-required mibs::

```python
mibParser = MibParser(mibs_paths='../cisco-mibs/*.my', idrs_list=['sysObjectID'], fast_load=True)
```

which will output the same as above. note - this method will run much slower because we need to first load all mib files
in mibs_paths and parse them.

two algorithms are available now using `fast_load` attribute. fast searching and fast loading. choose fast searching if
you have a lot of oids to search in small amount of mib files.

### example

clone and run directly MibParser which include some tests. you will see this output:

```text
using fast loading algorithm
Finished building test-dict-mib
saving test-dict-mib to D:\Eliav\IDF\SNMP Mibs\MibParser/tests/test-dict-mib.my
using fast loading algorithm
searching oid TimeTicks
searching oid frxT1OutOctets
searching oid dot1xPaeSystemAuthControl
searching oid frxH6EsTx
Finished building test-loading-mib
saving test-loading-mib to D:\Eliav\IDF\SNMP Mibs\MibParser/tests/test-loading-mib.my
execution time:0.2649993896484375
```

and 2 MIB files with 1400,700 lines of ASN1 definitions that was required to build mib that defines independently all
the required oids.

[see ./tests](./tests)<br/>
[example-1](./tests/test-dict-mib.my)<br/>
[example-2](./tests/test-loading-mib.my)<br/>

## Region

another very convenient class was implemented in this project in order to build MibParser. Region. is uses as a wrapper
for re.Match/re.Pattern regex classes which are not very convenient working with and sometimes confusing.<br/>
it's also very efficient to use in big string as it re-matches the original match and thus no need for copy part of the
string for later parsing.  
