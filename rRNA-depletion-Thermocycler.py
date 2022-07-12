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
    ctx.pause('HYB-DP1 Program')
    tc.close_lid()
    tc.set_lid_temperature(105)
    tc.set_block_temperature(95, hold_time_minutes=2)
    tc.set_block_temperature(37, ramp_rate=0.1)
    tc.deactivate_lid()
    tc.open_lid()
    ctx.pause('RNA_DEP Program')
    tc.open_lid()
    tc.set_lid_temperature(105)
    tc.set_block_temperature(37, hold_time_minutes=15)
    tc.set_block_temperature(4)
    tc.deactivate_lid()
    tc.open_lid()
    ctx.pause('PRB_REM Program')
    tc.close_lid()
    tc.set_lid_temperature(105)
    tc.set_block_temperature(37, hold_time_minutes=15)
    tc.set_block_temperature(4)
    tc.deactivate_lid()
    tc.open_lid()
    ctx.pause('NEB Fragment')
    tc.close_lid()
    tc.set_lid_temperature(105)
    tc.set_block_temperature(94, hold_time_minutes=15)
    tc.set_block_temperature(4)
    tc.deactivate_lid()
    tc.open_lid()
    ctx.pause('NEB First Strand cDNA')
    tc.close_lid()
    tc.set_lid_temperature(90)
    tc.set_block_temperature(25, hold_time_minutes=10)
    tc.set_block_temperature(42, hold_time_minutes=15)
    tc.set_block_temperature(70, hold_time_minutes=15)
    tc.set_block_temperature(4)
    tc.deactivate_lid()
    tc.open_lid()
    ctx.pause('NEB Second Strand cDNA')
    tc.close_lid()
    tc.set_lid_temperature(35)
    tc.set_block_temperature(16, hold_time_minutes=60)

