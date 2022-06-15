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
    # 1
    # 2
    # 3
    # 4 = Magnetic Module + PCR plate
    # 5 = Nest 12 reservoir (Oligo dT beads = max 480ul, RNA binding buffer = 6000)
    # 6 = Tips
    # 7 = Waste

    # Experiment Parameters
    sample_count = 8
    num_col = sample_count/8
    m300_mount = 'left'

    # Load labware
    labware_96_plate = 'nest_96_wellplate_100ul_pcr_full_skirt'
    res_type = 'nest_12_reservoir_15ml'
    tips300 = ctx.load_labware('opentrons_96_tiprack_300ul', '6','200µl filtertiprack')
    res1 = ctx.load_labware(res_type, '5', 'reagent reservoir 1')

    # Reagents
    beads = res1.wells()[0:1]
    buffer = res1.wells()[1:2]
    waste = res1.wells()[2:]


    # Modules
    mag = ctx.load_module('magnetic module gen2', '4')
    mag.disengage()
    magplate = mag.load_labware(labware_96_plate, 'Mag Plate')


    # P300M pipette
    m300 = ctx.load_instrument('p300_multi_gen2', m300_mount, tip_racks=tips300)


    # Helper functions

    def remove_supernatant(vol, park=False):
        """
        `remove_supernatant` will transfer supernatant from the deepwell
        extraction plate to the liquid waste reservoir.
        :param vol (float): The amount of volume to aspirate from all deepwell
                            sample wells and dispense in the liquid waste.
        :param park (boolean): Whether to pick up sample-corresponding tips
                               in the 'parking rack' or to pick up new tips.
        """

        m300.flow_rate.aspirate = 30
        num_trans = math.ceil(vol / 200)
        vol_per_trans = vol / num_trans
        for i, (m, spot) in enumerate(zip(mag_samples_m, parking_spots)):
            if park:
                _pick_up(m300, spot)
            else:
                _pick_up(m300)
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
            _drop(m300)
        m300.flow_rate.aspirate = 150

    def wash(vol, source, mix_reps=15, park=True, resuspend=True):
        """
        `wash` will perform bead washing for the extraction protocol.
        :param vol (float): The amount of volume to aspirate from each
                            source and dispense to each well containing beads.
        :param source (List[Well]): A list of wells from where liquid will be
                                    aspirated. If the length of the source list
                                    > 1, `wash` automatically calculates
                                    the index of the source that should be
                                    accessed.
        :param mix_reps (int): The number of repititions to mix the beads with
                               specified wash buffer (ignored if resuspend is
                               False).
        :param park (boolean): Whether to save sample-corresponding tips
                               between adding wash buffer and removing
                               supernatant.
        :param resuspend (boolean): Whether to resuspend beads in wash buffer.
        """

        if resuspend and magdeck.status == 'engaged':
            magdeck.disengage()

        num_trans = math.ceil(vol/200)
        vol_per_trans = vol/num_trans
        for i, (m, spot) in enumerate(zip(mag_samples_m, parking_spots)):
            _pick_up(m300)
            # side = 1 if i % 2 == 0 else -1
            # loc = m.bottom(0.5).move(Point(x=side*2))
            src = source[i//(12//len(source))]
            for n in range(num_trans):
                if m300.current_volume > 0:
                    m300.dispense(m300.current_volume, src.top())
                m300.transfer(vol_per_trans, src, m.top(), air_gap=20,
                              new_tip='never')
                if n < num_trans - 1:  # only air_gap if going back to source
                    m300.air_gap(20)
            if resuspend:
                # m300.mix(mix_reps, 150, loc)
                resuspend_pellet(m, m300, 180)
            m300.blow_out(m.top())
            m300.air_gap(20)
            if park:
                m300.drop_tip(spot)
            else:
                _drop(m300)

        if magdeck.status == 'disengaged':
            magdeck.engage(height=MAG_HEIGHT)

        ctx.delay(minutes=settling_time, msg='Incubating on MagDeck for \
' + str(settling_time) + ' minutes.')

        remove_supernatant(vol, park=park)

    def add_beads(bead_loc, cols):
        current_col = 0
        while current_col < cols:
            m300.distribute(20, res1.wells_by_name(bead_loc),magplate)
            current_col += 1

    add_beads('beads',1)
