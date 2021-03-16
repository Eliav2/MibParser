## Python MibParser
a simple mib parser.
I did not like all the complicated parser out there, and which i encountered a lot of bugs, so I wrote my own parser.

this is not general parser - the main usage of this parser: 
collect and build a mib file from multiple mib files based on given oid-names.
it will recursively collect all dependent oids and types to a single mib file, in the same order as mentioned.

### Example:
let's say you want to build a mib for the oid sysObjectID which defined in RFC1213-MIB.my in the current directory.
also note that you have to include all dependent mib files in the same directory.
so:
```python
from MibParser import MibParser
mibCollector = MibParser({"sysObjectID": "RFC1213-MIB.my"})
mib_text = mibCollector.eject_mib()
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

this independent mib file constructed from RFC1213-MIB.my(the direct dependent) and from RFC1155-SMI.my(second dependent).
you can see and run more complicated example by running directly MibParser.py.
