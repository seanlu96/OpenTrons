metadata = {
    'protocolName': '''NEBNext Ultra II Directional RNA Library Prep Kit
    for Illumina with poly(A) selection: part 0 - Bead wash''',
    'author': 'Sean Lu',
    'apiLevel': '2.9'
}

from opentrons.types import Point
import json
import os
import math
from opentrons import types

def run(ctx):

    # Deck Overview
    # 1 Magnetic Module + PCR plate
    # 2 Nest 12 reservoir (Oligo dT beads = max 480ul, RNA binding buffer = 6000)
    # 3 Temperature module (RNA sample)
    # 4 Waste
    # 5 Tips
    # 6

    # Experiment Parameters
    sample_count = 16
    num_cols = int(sample_count/8)
    m300_mount = 'left'


    # Load labware
    labware_96_plate = 'nest_96_wellplate_100ul_pcr_full_skirt'
    res_type = 'nest_12_reservoir_15ml'
    tips300 = [ctx.load_labware('opentrons_96_tiprack_300ul', '5', '200µl filtertiprack')]
    res1 = ctx.load_labware(res_type, '2', 'reagent reservoir 1')
    parking_spots = [None for none in range(12)]

    # Reagents
    beads = res1.wells()[0:1]  #Oligo dT Beads = num samples * 20ul * 1.5
    wash = res1.wells()[1:2]  #RNA Binding Buffer (2X) = num_samples * 250ul * 1.5
    waste = res1.wells()[11]



    # Modules
    mag = ctx.load_module('magnetic module gen2', '1')
    mag_gen = 'magnetic module gen2'
    mag.disengage()
    magplate = mag.load_labware(labware_96_plate, 'Mag Plate')
    mag_samples_m = magplate.rows()[0][:num_cols]
    if mag_gen == 'magdeck':
        MAG_HEIGHT = 13.6
    else:
        MAG_HEIGHT = 6.8
    tempdeck = ctx.load_module('Temperature Module Gen2', '3')
    rnaplate = tempdeck.load_labware(
        'opentrons_96_aluminumblock_nest_wellplate_100ul')
    tempdeck.set_temperature(4)

    # P300M pipette
    m300 = ctx.load_instrument('p300_multi_gen2', m300_mount, tip_racks=tips300)

    # Waste Tracking
    waste_vol = 0
    waste_well = 3
    waste_threshold = 15000


    def remove_supernatant(vol, park=False):
        """
        `remove_supernatant` will transfer supernatant from the deepwell
        extraction plate to the liquid waste reservoir.
        :param vol (float): The amount of volume to aspirate from all deepwell
                            sample wells and dispense in the liquid waste.
        :param park (boolean): Whether to pick up sample-corresponding tips
                               in the 'parking rack' or to pick up new tips.
        """

        def _waste_track(vol):
            nonlocal waste_vol
            if waste_vol + vol >= waste_threshold:
                # Setup for flashing lights notification to empty liquid waste

                m300.home()
                ctx.pause('Please empty liquid waste (slot 11) before \ resuming.')
                ctx.home()  # home before continuing with protocol
                waste_vol = 0
            waste_vol += vol

        m300.flow_rate.aspirate = 30
        num_trans = math.ceil(vol / 200)
        vol_per_trans = vol / num_trans
        m300.pick_up_tip()
        for i, (m, spot) in enumerate(zip(mag_samples_m, parking_spots)):
            side = -1 if i % 2 == 0 else 1
            loc = m.bottom(0.5).move(Point(x=side * 2))
            for _ in range(num_trans):
                _waste_track(vol_per_trans)
                if m300.current_volume > 0:
                    # void air gap if necessary
                    m300.dispense(m300.current_volume, m.top())
                m300.move_to(m.center())
                m300.transfer(vol_per_trans, loc, waste, new_tip='never',
                              air_gap=20)
                m300.blow_out(waste)
                m300.air_gap(20)
            # m300.drop_tip()
        m300.drop_tip()
        m300.flow_rate.aspirate = 150


    m300.flow_rate.aspirate = 30
    m300.distribute(20, beads, magplate.columns()[0:num_cols], disposal_volume=10, mix_before=(6,15))
    m300.flow_rate.aspirate = 75
    m300.flow_rate.dispense = 75
    m300.distribute(100,wash,magplate.columns()[0:num_cols],disposal_volume=50, mix_after=(6,100))
    mag.engage()
    ctx.delay(minutes=3)
    remove_supernatant(100)
    mag.disengage()
    m300.distribute(100, wash, magplate.columns()[0:num_cols], disposal_volume=50, mix_after=(6, 100))
    mag.engage()
    ctx.delay(minutes=3)
    remove_supernatant(100)
    mag.disengage()
    m300.distribute(50, wash, magplate.columns()[0:num_cols], disposal_volume=50, mix_after=(6, 100))
    m300.flow_rate.aspirate = 30
    m300.transfer(50, magplate.columns()[0:num_cols], rnaplate.columns()[0:num_cols], mix_before=(6,40), mix_after=(6,45),
                  air_gap=10)



