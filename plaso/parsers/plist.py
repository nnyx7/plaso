# -*- coding: utf-8 -*-
"""This file contains the Property List (Plist) Parser.

Plaso's engine calls PlistParser when it encounters Plist files to be processed.
"""

import binascii
import logging

from binplist import binplist

from plaso.lib import errors
from plaso.lib import utils
from plaso.parsers import interface
from plaso.parsers import manager


class PlistParser(interface.FileObjectParser):
  """De-serializes and parses plists the event objects are generated by plist.

  The Plaso engine calls parsers by their Parse() method. This parser's
  Parse() has GetTopLevel() which deserializes plist files using the binplist
  library and calls plugins (PlistPlugin) registered through the
  interface by their Process() to produce event objects.

  Plugins are how this parser understands the content inside a plist file,
  each plugin holds logic specific to a particular plist file. See the
  interface and plist_plugins/ directory for examples of how plist plugins are
  implemented.
  """

  NAME = u'plist'
  DESCRIPTION = u'Parser for binary and text plist files.'

  _plugin_classes = {}

  def __init__(self):
    """Initializes a parser object."""
    super(PlistParser, self).__init__()
    self._plugins = PlistParser.GetPluginObjects()

  def GetTopLevel(self, file_object, file_name=u''):
    """Returns the deserialized content of a plist as a dictionary object.

    Args:
      file_object: A file-like object to parse.
      file_name: The name of the file-like object.

    Returns:
      A dictionary object representing the contents of the plist.
    """
    # Note that binplist.readPlist does not seek to offset 0.
    try:
      top_level_object = binplist.readPlist(file_object)
    except binplist.FormatError as exception:
      # TODO: remove need for GetUnicodeString.
      error_string = utils.GetUnicodeString(exception)
      raise errors.UnableToParseFile(
          u'File is not a plist file: {0:s}'.format(error_string))
    except (
        LookupError, binascii.Error, ValueError, AttributeError) as exception:
      raise errors.UnableToParseFile(
          u'Unable to parse XML file, reason: {0:s}'.format(exception))
    except OverflowError as exception:
      raise errors.UnableToParseFile(
          u'Unable to parse: {0:s} with error: {1:s}'.format(
              file_name, exception))

    if not top_level_object:
      error_string = utils.GetUnicodeString(exception)
      raise errors.UnableToParseFile(
          u'File is not a plist: {0:s}'.format(error_string))

    # Since we are using readPlist from binplist now instead of manually
    # opening  the binary plist file we loose this option. Keep it commented
    # out for now but this needs to be tested a bit more.
    # TODO: Re-evaluate if we can delete this or still require it.
    #if bpl.is_corrupt:
    #  logging.warning(
    #      u'Corruption detected in binary plist: {0:s}'.format(file_name))

    return top_level_object

  def ParseFileObject(self, parser_mediator, file_object, **unused_kwargs):
    """Parses a plist file-like object.

    Args:
      parser_mediator: A parser mediator object (instance of ParserMediator).
      file_object: A file-like object.

    Raises:
      UnableToParseFile: when the file cannot be parsed.
    """
    filename = parser_mediator.GetFilename()
    file_size = file_object.get_size()

    if file_size <= 0:
      raise errors.UnableToParseFile(
          u'File size: {0:d} bytes is less equal 0.'.format(file_size))

    # 50MB is 10x larger than any plist seen to date.
    if file_size > 50000000:
      raise errors.UnableToParseFile(
          u'File size: {0:d} bytes is larger than 50 MB.'.format(file_size))

    top_level_object = None
    try:
      top_level_object = self.GetTopLevel(file_object, filename)
    except errors.UnableToParseFile:
      raise

    if not top_level_object:
      raise errors.UnableToParseFile(
          u'Unable to parse: {0:s} skipping.'.format(filename))

    for plugin_object in self._plugins:
      try:
        plugin_object.UpdateChainAndProcess(
            parser_mediator, plist_name=filename, top_level=top_level_object)

      except errors.WrongPlistPlugin as exception:
        logging.debug(u'Wrong plugin: {0:s} for: {1:s}'.format(
            exception.args[0], exception.args[1]))


manager.ParsersManager.RegisterParser(PlistParser)
