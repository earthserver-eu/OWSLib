#############################################
#Author:        Damiano Barboni <barboni@meeo.it>
#Description:   Parse and manage wcs2 getCoverage XML
#############################################

from xml.dom.minidom import *
import datetime
import sys

knownLabels = {
    "t": [ "t", "unix", "ansi", "date", "reftime", "time", "d" ],
    "x": [ "Long", "E" ],
    "y": [ "Lat", "N"]
}

fmt_list = [ '%Y.%m.%d %H:%M:%S',
             '%Y%m%d %H:%M:%S',
             '%Y-%m-%dT%H:%M:%SZ',
             '%Y-%m-%dT%H:%M:%S.%fZ',
             '%Y-%m-%d %H:%M:%S',
             '%Y.%m.%d',
             '%Y%m%d',
             '%Y-%m-%d' ]

#return data formatted in a timely manner
#{date:tile_data (x*y matrix)}
class CoverageDataParser():
    def __init__( self, xml, log = None ):

        self.xml       = xml
        self.dom = parseString( self.xml )
        self.getTupleList()
        self.xPos      = self.getAxisPosition( "x" )
        self.yPos      = self.getAxisPosition( "y" )
        self.tPos      = self.getAxisPosition( "t" )
        self.getTResolution()
        self.getEnvelope()
        self.getGridEnvelope()

    def getAxisPosition( self, axis_type ):
        #ansi Lat Long
        for i, label in enumerate( self.getLabels() ):
            if label in knownLabels[ axis_type ]:
                return i

    def getLabels( self ):
        tag = self.dom.getElementsByTagName('Envelope')
        self.labels = tag[0].getAttribute( "axisLabels" ).split(" ")
        return self.labels

    def getUoms( self ):
        tag = self.dom.getElementsByTagName('Envelope')
        self.uoms = tag[0].getAttribute( "uomLabels" ).split(" ")
        return self.uoms

    def getTupleList( self ):
        tag = self.dom.getElementsByTagName('tupleList')
        self.tupleList = [ float(i) for i in tag[0].firstChild.nodeValue.split( "," ) ]
        return self.tupleList

    def getCoefficients( self ):
        try:
            tag       = self.dom.getElementsByTagName('gmlrgrid:coefficients')
            coefficients = [ float(i) * self.tResolution for i in tag[ self.tPos ].firstChild.nodeValue.split() ]
        except:
            #try rasdaman workaround
            tag = self.dom.getElementsByTagName('offsetVector')
            coefficients = [ i * self.tResolution for i in range( 0, ( self.high[ self.tPos ] - self.low[ self.tPos ] ) + 1 ) ]
        return coefficients

    def srsName( self ):
        tag = self.dom.getElementsByTagName('Envelope')
        return tag[0].getAttribute("srsName")

    def getPxResolution( self ):
        for offsetVector in [ 'offsetVector', 'gmlrgrid:offsetVector' ]:
            tags = self.dom.getElementsByTagName( offsetVector )
            if tags:
                for tag in tags:
                    node_value = tag.firstChild.nodeValue.split( " " )
                    self.pxResolution = float( node_value[ self.xPos ] )
                    if self.pxResolution != 0:
                        break
                break
        return self.pxResolution

    #return temporal resolution in seconds
    def getTResolution( self ):
        for offsetVector in [ 'offsetVector', 'gmlrgrid:offsetVector' ]:
            tags = self.dom.getElementsByTagName( offsetVector )
            if tags:
                for tag in tags:
                    node_value = tag.firstChild.nodeValue.split( " " )
                    tResolution = float( node_value[ self.tPos ] )
                    if tResolution != 0:
                        break
                break
        t_uoms = self.getUoms()[ self.tPos ]
        if t_uoms == "s":
            self.tResolution = tResolution
        elif t_uoms == "d":
            self.tResolution = tResolution * 24 * 60 * 60
        else:
            print ( "T reslution %s not recognized" %( t_uoms ) )
            self.tResolution = tResolution

    def _toDate( self, d ):
        t_uoms = self.getUoms()[ self.tPos ]
        if t_uoms == "s":
            #TODO assume unix for now so origin is 1970-01-01T00:00:00
            delta  = datetime.timedelta( seconds = float( d ) )
            origin = datetime.datetime(1970, 1, 1, 0, 0, 0)
            gregorian_date = origin + delta
            return gregorian_date
        else: #if t_uoms == "d":
            #TODO assume ansi for now
            #ANSI Date origin January 1, 1601, Monday (as Day 1)
            try:
                delta  = datetime.timedelta( days = float( d ) )
                origin = datetime.datetime(1600,12,31,0,0)
                gregorian_date = origin + delta
                return gregorian_date
            except:
                #remove quote from string
                d = d.strip('"').strip("'")
                for fmt in fmt_list:
                    try:
                        gregorian_date = datetime.datetime.strptime( d, fmt )
                        return gregorian_date
                    except:
                        None

    def getEnvelope( self ):
        t_uoms = self.getUoms()[ self.tPos ]
        #geographic coordinate
        tag = self.dom.getElementsByTagName('lowerCorner')
        node_value = tag[0].firstChild.nodeValue.split()
        self.lowerCorner = []
        self.lowerCorner.append( float( node_value[ self.xPos ] ) )
        self.lowerCorner.append( float( node_value[ self.yPos ] ) )
        self.lowerCorner.append( self._toDate( node_value[ self.tPos ] ) )

        tag = self.dom.getElementsByTagName('upperCorner')
        node_value = tag[0].firstChild.nodeValue.split()
        self.upperCorner = []
        self.upperCorner.append( float( node_value[ self.xPos ] ) )
        self.upperCorner.append( float( node_value[ self.yPos ] ) )
        self.upperCorner.append( self._toDate( node_value[ self.tPos ] ) )
        return {
            "lowerCorner": self.lowerCorner,
            "upperCorner": self.upperCorner
        }

    def getGridEnvelope( self ):
        #raster coordinates
        tag = self.dom.getElementsByTagName('low')
        self.low = [ int(i) for i in tag[0].firstChild.nodeValue.split() ]
        tag = self.dom.getElementsByTagName('high')
        self.high = [ int(i) for i in tag[0].firstChild.nodeValue.split() ]
        return { "low": self.low, "high": self.high }

    def getOrigin( self ):
        #gml:origin origin position
        tag = self.dom.getElementsByTagName('gml:pos')
        if len( tag ) == 0:
            tag = self.dom.getElementsByTagName('pos')
        node_value = tag[0].firstChild.nodeValue.split()
        self.origin = []
        self.origin.append( float( node_value[ self.xPos ] ) )
        self.origin.append( float( node_value[ self.yPos ] ) )
        self.origin.append( self.lowerCorner[ -1 ] ) #workarounf for rasdaman bug - use lowerCorner t
        return self.origin

    def getX(self):
        xdata = []
        for coeff in self.getCoefficients():
            delta  = datetime.timedelta( seconds = coeff )
            target_date = self.lowerCorner[ -1 ] + delta
            xdata.append( target_date )
        return xdata

    def getY( self ):
        return self.tupleList

if __name__ == "__main__":
    xml = open( sys.argv[1], "r" )
    xml_text = xml.read()
    xml.close()
    cdp = CoverageDataParser( xml_text )
    print (len(cdp.getX()))
    print (len(cdp.getY()))

