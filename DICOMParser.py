import pydicom, os, json


class DICOMParser:
  def __init__(self,fileName,rulesDictionary,dcmqiPath=None,tempPath=None):
    try:
      self.dcm = pydicom.read_file(fileName)
    except:
      raise

    self.fileName = fileName
    self.rulesDictionary = rulesDictionary
    self.tempPath = tempPath
    self.dcmqiPath = dcmqiPath

    self.tables = {}

  def getTables(self):
    return self.tables

  def parse(self):
    self.readReferences()

    modality = self.dcm.Modality

    if modality in ["SR","PT","CT","SEG","RWV"]:
      self.readTopLevelAttributes(self.dcm.Modality)

    if modality == "SEG":
      self.readSegments()
      self.readSegmentFrames()

    if modality == "SR":
      tid = self.dcm.ContentTemplateSequence[0].TemplateIdentifier
      if tid == "1500":
        # convert to JSON
        from subprocess import call
        outputJSON = os.path.join(self.tempPath,"measurements.json")
        tid1500reader = os.path.join(self.dcmqiPath,"tid1500reader")
        print tid1500reader
        call([tid1500reader,"--inputDICOM",self.fileName,"--outputMetadata",outputJSON])
        with open(outputJSON) as jsonFile:
          measurementsJSON = json.load(jsonFile)
          self.readMeasurements(measurementsJSON)

  def readTopLevelAttributes(self,modality):
    self.tables[modality] = {}
    unresolvedAttributes = []
    for a in self.rulesDictionary[modality]:
      try:
        dataElement = self.dcm.data_element(a)
        if dataElement.VM>1:
          self.tables[modality][a] = '/'.join([str(i) for i in dataElement.value])
        else:
          self.tables[modality][a] = str(dataElement.value)
#        else:
#          self.tables[table]
#        self.tables[tableName][a] = self.dcm.data_element(a).value
#        print self.dcm.data_element(a).VM
      except:
        unresolvedAttributes.append(a)
        self.tables[modality][a] = None

    for a in unresolvedAttributes:
      if hasattr(self,"read"+modality+a):
         resolvedAttribute = str(getattr(self, "read%s%s" % (modality, a) )())
         self.tables[modality][a] = resolvedAttribute
         '''
         if resolvedAttribute is not None:
           print "Successfully resolved",a
         else:
           print "Failed to resolve",a
         '''

      #print self.tables[tableName][a]

  # functions to read specific attributes that are not top-level or that are SR #   tree elements
  #def readReferencedImageRealWorldValueMappingSequence(self):
  #  de = self.dcm.data_element("ReferencedImageRealWorldValueMappingSequence")
  #  if de:
  #    de = de.data_element("RealWorldValueMappingSequence")
  #    if de:

  # given the input data element, which must be a SQ, and must have the structure
  #  of items that follow the pattern ConceptNameCodeSequence/ConceptCodeSequence, find the sequence item that has
  #  ConceptNameCodeSequence > CodeMeaning, and return the data element corresponding
  #  to the ConceptCodeSequnce matching the requested ConceptNameCodeSequence meaning
  def getConceptCodeByConceptNameMeaning(self,dataElement,conceptNameMeaning):
    for item in dataElement:
      if item.ConceptNameCodeSequence[0].CodeMeaning == conceptNameMeaning:
        return item.ConceptCodeSequence[0]
    return None

  def getMeasurementUnitsCodeSequence(self):
    dataElement = self.getRWMSequence()
    return dataElement.data_element("MeasurementUnitsCodeSequence").value

  def getQuantityDefinitionSequence(self):
    dataElement = self.getRWMSequence()
    return dataElement.data_element("QuantityDefinitionSequence").value

  def getRWMSequence(self):
    dataElement = self.dcm.data_element("ReferencedImageRealWorldValueMappingSequence").value[0]
    return dataElement.data_element("RealWorldValueMappingSequence").value[0]

  def readRWVUnits_CodeValue(self):
    dataElement = self.getMeasurementUnitsCodeSequence()[0]
    return dataElement.CodeValue

  def readRWVUnits_CodingSchemeDesignator(self):
    dataElement = self.getMeasurementUnitsCodeSequence()[0]
    return dataElement.CodingSchemeDesignator

  def readRWVUnits_CodeMeaning(self):
    dataElement = self.getMeasurementUnitsCodeSequence()[0]
    return dataElement.CodeMeaning

  def readRWVQuantity_CodeValue(self):
    dataElement = self.getQuantityDefinitionSequence()
    dataElement = self.getConceptCodeByConceptNameMeaning(dataElement, "Quantity")
    return dataElement.CodeValue

  def readRWVQuantity_CodingSchemeDesignator(self):
    dataElement = self.getQuantityDefinitionSequence()
    dataElement = self.getConceptCodeByConceptNameMeaning(dataElement, "Quantity")
    return dataElement.CodingSchemeDesignator

  def readRWVQuantity_CodeMeaning(self):
    dataElement = self.getQuantityDefinitionSequence()
    dataElement = self.getConceptCodeByConceptNameMeaning(dataElement, "Quantity")
    return dataElement.CodeMeaning

  def readRWVMeasurementMethod_CodeValue(self):
    dataElement = self.getQuantityDefinitionSequence()
    dataElement = self.getConceptCodeByConceptNameMeaning(dataElement, "Measurement Method")
    return dataElement.CodeValue

  def readRWVMeasurementMethod_CodingSchemeDesignator(self):
    dataElement = self.getQuantityDefinitionSequence()
    dataElement = self.getConceptCodeByConceptNameMeaning(dataElement, "Measurement Method")
    return dataElement.CodingSchemeDesignator

  def readRWVMeasurementMethod_CodeMeaning(self):
    dataElement = self.getQuantityDefinitionSequence()
    dataElement = self.getConceptCodeByConceptNameMeaning(dataElement, "Measurement Method")
    return dataElement.CodeMeaning

  def readRWVRealWorldValueIntercept(self):
    dataElement = self.getRWMSequence()
    return dataElement.RealWorldValueIntercept

  def readRWVRealWorldValueSlope(self):
    dataElement = self.getRWMSequence()
    return dataElement.RealWorldValueSlope

  # this part is not driven at all by the QDBD schema!
  #  (maybe it should be changed to generalize things better)
  def readReferences(self):
    self.tables["References"] = []
    try:
      refSeriesSeq = self.dcm.data_element("ReferencedSeriesSequence")
    except:
      refSeriesSeq = None
    try:
      evidenceSeq = self.dcm.data_element("CurrentRequestedProcedureEvidenceSequence")
    except:
      evidenceSeq = None

    if refSeriesSeq:
      self.readReferencedSeriesSequence(refSeriesSeq)
    if evidenceSeq:
      self.readEvidenceSequence(evidenceSeq)

  def readReferencedSeriesSequence(self, seq):
    for r in seq:
      seriesUID = r.data_element("SeriesInstanceUID").value
      refInstancesSeq = r.data_element("ReferencedInstanceSequence").value
      for i in refInstancesSeq:
        refClassUID = i.ReferencedSOPClassUID
        refInstanceUID = i.ReferencedSOPInstanceUID

        self.tables["References"].append({"SOPInstanceUID": self.dcm.SOPInstanceUID,
                                          "ReferencedSOPClassUID": refClassUID,
                                          "ReferencedSOPInstanceUID": refInstanceUID,
                                          "SeriesInstanceUID": seriesUID})

  def readEvidenceSequence(self, seq):
    for l1item in seq:
      seriesSeq = l1item.data_element("ReferencedSeriesSequence").value
      for l2item in seriesSeq:
        sopSeq = l2item.data_element("ReferencedSOPSequence").value
        seriesUID = l2item.SeriesInstanceUID
        for l3item in sopSeq:
          refClassUID = l3item.ReferencedSOPClassUID
          refInstanceUID = l3item.ReferencedSOPInstanceUID

          self.tables["References"].append({"SOPInstanceUID": self.dcm.SOPInstanceUID,
                                            "ReferencedSOPClassUID": refClassUID,
                                            "ReferencedSOPInstanceUID": refInstanceUID,
                                            "SeriesInstanceUID": seriesUID})

  def readSegments(self):
    seq = self.dcm.data_element("SegmentSequence")
    self.tables["SEG_Segments"] = []

    for segment in seq:
      sAttr = {}

      # Attribute should be either in a sub-sequence, at the
      #  top level of the sequence, or at the top level of the dataset
      #  Try all those options
      for attr in self.rulesDictionary["SEG_Segments"]:
        if attr.find("_")>0:
          # it is (supposed to be!) a code tuple in a sequence
          seqName,attrName = attr.split("_")
          try:
            sAttr[attr] = segment.data_element(seqName)[0].data_element(attrName).value
          except:
            continue
        else:
          try:
            sAttr[attr] = segment.data_element(attr).value
          except:
            try:
              sAttr[attr] = self.dcm.data_element(attr).value
            except:
              sAttr[attr] = None

      self.tables["SEG_Segments"].append(sAttr)

  def readSegmentFrames(self):
    pfFG = self.dcm.data_element("PerFrameFunctionalGroupsSequence")
    sFG = self.dcm.data_element("SharedFunctionalGroupsSequence")

    self.tables["SEG_SegmentFrames"] = []

    # Attrubute should be either in a sub-sequence, in the shared FG,
    #  or at the top level of the dataset
    #  Try all those options
    for frame in pfFG:
      fAttr = {}
      for attr in self.rulesDictionary["SEG_SegmentFrames"]:
        # print "Looking for",attr
        # recursively search in the per-frame FG item
        value = self.recursiveFindInDataset(frame,attr)
        if value is None:
          # recursively search in the shared FG
          value = self.recursiveFindInDataElement(sFG,attr)
        # if those fail, look it up top-level
        if value is None:
          value = self.dcm.data_element(attr).value
        fAttr[attr] = value
      self.tables["SEG_SegmentFrames"].append(fAttr)

  # idea from https://github.com/pieper/Chronicle/blob/master/bin/record.py#L58
  def recursiveFindInDataElement(self,de,attr):
    if de.keyword == attr:
      return de.value
    elif de.VR == "SQ":
      for item in de:
        return self.recursiveFindInDataset(item,attr)
    return None

  def recursiveFindInDataset(self,ds,attr):
    for key in ds.keys():
      de = ds[key]
      value = self.recursiveFindInDataElement(de,attr)
      if value is not None:
        return value
    return None

  def readMeasurements(self,measurements):
    self.tables["SR1500_MeasurementGroups"] = []
    self.tables["SR1500_Measurements"] = []

    for mg in measurements["Measurements"]:
      mAttr = {}
      for attr in self.rulesDictionary["SR1500_MeasurementGroups"]:
        # first try to find it in the top-level of the measurements group json
        if attr in mg.keys():
          value = mg[attr]
        elif attr.find("_")>0:
          # this is a code sequence
          concept = attr.split("_")[0]
          item = attr.split("_")[1]
          value = mg[concept][item]
        else:
          # if all other attempts fail, read it at the top level of the
          #   DICOM dataset (it must be a foreign key)
          value = self.dcm.data_element(attr).value
        mAttr[attr] = value

      self.tables["SR1500_MeasurementGroups"].append(mAttr)

      for mi in mg["measurementItems"]:
        miAttr = {}
        # OMG! Such a terrible code duplication
        for iattr in self.rulesDictionary["SR1500_Measurements"]:
          # first try to find it in the top-level of the measurements group json
          if iattr in mi.keys():
            value = mi[iattr]
          elif iattr.find("_")>0:
            # this is a code sequence
            concept = iattr.split("_")[0]
            item = iattr.split("_")[1]
            try:
              value = mi[concept][item]
            except:
              continue
          # the attribute is one level above!
          #  our secondary foreign key is TrackingUniqueIdentifier ...
          # So this is a tiny bit different from the code above!
          elif iattr in mAttr.keys():
            value = mAttr[iattr]
          else:
            # if all other attempts fail, read it at the top level of the
            #   DICOM dataset (it must be a foreign key)
            value = self.dcm.data_element(iattr).value

          miAttr[iattr] = value
        self.tables["SR1500_Measurements"].append(miAttr)
