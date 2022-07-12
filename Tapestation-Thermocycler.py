from opentrons.types import Point
import json
import os
import math
from opentrons import types

metadata = {
    'protocolName': 'RNA Tapestation Thermocycler Steps',
    'author': 'Sean Lu',
    'apiLevel': '2.8'
}

def run(ctx):
    tc = ctx.load_module('thermocycler')
    ctx.pause('Load samples')
    tc.close_lid()
    tc.set_block_temperature(72, hold_time_minutes=3)
    tc.set_block_temperature(4)
    tc.open_lid()

