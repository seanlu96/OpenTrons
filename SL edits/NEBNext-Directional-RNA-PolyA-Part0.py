metadata = {
    'protocolName': '''NEBNext Ultra II Directional RNA Library Prep Kit
    for Illumina with poly(A) selection: part 0 - Bead wash''',
    'author': 'Sean Lu',
    'apiLevel': '2.9'
}

#

from opentrons.types import Point
import json
import os
import math
from opentrons import types

def run(ctx):

    # Deck Overview
    # 1
    # 2
    # 3 Temperature module (RNA sample)
    # 4 Magnetic module + PCR plate
    # 5 Nest 12 reservoir (Oligo dT beads = max 480ul, RNA binding buffer = 6000)
    # 6 Tips
    # 7 Thermocycler-1
    # 8 Thermocycler-2
    # 9
    # 10 Thermocycler-3
    # 11 Thermocycler-4


    # Experiment Parameters
    sample_count = 24
    num_cols = int(sample_count/8)
    m300_mount = 'left'
    park_tips = True

    # Load labware
    labware_96_plate = 'nest_96_wellplate_100ul_pcr_full_skirt'
    res_type = 'nest_12_reservoir_15ml'
    tips300 = [ctx.load_labware('opentrons_96_tiprack_300ul', '6', '200µl filtertiprack')]
    res1 = ctx.load_labware(res_type, '5', 'reagent reservoir 1')
    if park_tips:
        parkingrack = ctx.load_labware(
            'opentrons_96_tiprack_300ul', '1', 'tiprack for parking')
        parking_spots = parkingrack.rows()[0][:num_cols]
    else:
        tips300.insert(0, ctx.load_labware('opentrons_96_tiprack_300ul', '1',
                                           '200µl filtertiprack'))
        parking_spots = [None for none in range(12)]

    # Reagents
    beads = res1.wells()[0:1]  #Oligo dT Beads = num samples * 20ul * 1.5
    RNA_buffer = res1.wells()[1:2]  #RNA Binding Buffer (2X) = num_samples * 250ul * 1.5
    waste = res1.wells()[11]



    # Modules
    magdeck = ctx.load_module('magnetic module gen2', '4')
    mag_gen = 'magnetic module gen2'
    magdeck.disengage()
    magplate = magdeck.load_labware(labware_96_plate, 'Mag Plate')
    mag_samples_m = magplate.rows()[0][:num_cols]
    if mag_gen == 'magdeck':
        MAG_HEIGHT = 13.6
    else:
        MAG_HEIGHT = 6.8
    tempdeck = ctx.load_module('Temperature Module Gen2', '3') #unused
    tc = ctx.load_module('Thermocycler Module')
    rnaplate = tc.load_labware('opentrons_96_aluminumblock_nest_wellplate_100ul')


    # Pipettes
    m300 = ctx.load_instrument('p300_multi_gen2', m300_mount, tip_racks=tips300)
    m300.flow_rate.aspirate = 50
    m300.flow_rate.dispense = 150
    m300.flow_rate.blow_out = 300

    #Tip tracking and helper functions
    tip_track = False  # Track tips on pipette
    tip_log = {val: {} for val in ctx.loaded_instruments.values()}

    folder_path = '/data/B'
    tip_file_path = folder_path + '/tip_log.json'
    if tip_track and not ctx.is_simulating():
        if os.path.isfile(tip_file_path):
            with open(tip_file_path) as json_file:
                data = json.load(json_file)
                for pip in tip_log:
                    if pip.name in data:
                        tip_log[pip]['count'] = data[pip.name]
                    else:
                        tip_log[pip]['count'] = 0
        else:
            for pip in tip_log:
                tip_log[pip]['count'] = 0
    else:
        for pip in tip_log:
            tip_log[pip]['count'] = 0

    for pip in tip_log:
        if pip.type == 'multi':
            tip_log[pip]['tips'] = [tip for rack in pip.tip_racks
                                    for tip in rack.rows()[0]]
        else:
            tip_log[pip]['tips'] = [tip for rack in pip.tip_racks
                                    for tip in rack.wells()]
        tip_log[pip]['max'] = len(tip_log[pip]['tips'])

    def _pick_up(pip, loc=None):
        if tip_log[pip]['count'] == tip_log[pip]['max'] and not loc:
            ctx.set_rail_lights(False)
            ctx.pause('Replace ' + str(pip.max_volume) + 'µl tipracks before \
    resuming.')
            ctx.set_rail_lights(True)
            pip.reset_tipracks()
            tip_log[pip]['count'] = 0
        if loc:
            pip.pick_up_tip(loc)
        else:
            pip.pick_up_tip(tip_log[pip]['tips'][tip_log[pip]['count']])
            tip_log[pip]['count'] += 1

    switch = True
    drop_count = 0
    # number of tips trash will accommodate before prompting user to empty
    drop_threshold = 193  # Was 120

    def _drop(pip):
        nonlocal switch
        nonlocal drop_count
        side = 30 if switch else -18
        drop_loc = ctx.loaded_labwares[12].wells()[0].top().move(
            Point(x=side))
        pip.drop_tip(drop_loc)
        switch = not switch
        if pip.type == 'multi':
            drop_count += 8
        else:
            drop_count += 1
        if drop_count >= drop_threshold:
            # Setup for flashing lights notification to empty trash
            m300.home()
            ctx.set_rail_lights(False)
            ctx.pause('Please empty tips from waste before resuming.')
            ctx.set_rail_lights(True)
            ctx.home()  # home before continuing with protocol
            drop_count = 0


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
        m300.drop_tip() #TODO: check if drop tip can be here
        m300.flow_rate.aspirate = 150

    def resuspend_pellet(well, pip, mvol, reps=5):
        """
        'resuspend_pellet' will forcefully dispense liquid over the
        pellet after the magdeck engage in order to more thoroughly resuspend
        the pellet.param well: The current well that the resuspension will
        occur in. param pip: The pipet that is currently attached/ being used.
        param mvol: The volume that is transferred before the mixing steps.
        param reps: The number of mix repetitions that should occur. Note~
        During each mix rep, there are 2 cycles of aspirating from center,
        dispensing at the top and 2 cycles of aspirating from center,
        dispensing at the bottom (5 mixes total)
        """

        rightLeft = int(str(well).split(' ')[0][1:]) % 2
        """
        'rightLeft' will determine which value to use in the list of 'top' and
        'bottom' (below), based on the column of the 'well' used.
        In the case that an Even column is used, the first value of 'top' and
        'bottom' will be used, otherwise,
        the second value of each will be used.
        """
        center = well.bottom().move(types.Point(x=0, y=0, z=0.5))
        top = [
            well.bottom().move(types.Point(x=-3.8, y=3.8, z=10)),
            well.bottom().move(types.Point(x=3.8, y=3.8, z=10))
        ]
        bottom = [
            well.bottom().move(types.Point(x=-3.8, y=-3.8, z=10)),
            well.bottom().move(types.Point(x=3.8, y=-3.8, z=10))
        ]

        pip.flow_rate.dispense = 500
        pip.flow_rate.aspirate = 150

        mix_vol = 0.9 * mvol

        pip.move_to(center)
        for _ in range(reps):
            for _ in range(2):
                pip.aspirate(mix_vol, center)
                pip.dispense(mix_vol, top[rightLeft])
            for _ in range(2):
                pip.aspirate(mix_vol, center)
                pip.dispense(mix_vol, bottom[rightLeft])

    def add_beads(vol, source, park=False):
        total_vol = vol*num_cols
        m300.distribute(vol, source, magplate.columns()[0:num_cols], disposal_volume=5, mix_before=(6,0.9*vol))

    def wash(vol, source, mix_reps=15, park=True, resuspend=True, delay_time=2, discard_supernatant=True):
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

        num_trans = math.ceil(vol / 200)
        vol_per_trans = vol / num_trans
        for i, (m, spot) in enumerate(zip(mag_samples_m, parking_spots)):
            _pick_up(m300)
            # side = 1 if i % 2 == 0 else -1
            # loc = m.bottom(0.5).move(Point(x=side*2))
            src = source[i // (12 // len(source))]
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

        if discard_supernatant:
            if magdeck.status == 'disengaged':
                magdeck.engage(height=MAG_HEIGHT)

            ctx.delay(minutes=delay_time, msg='Incubating on MagDeck for \
    ' + str(delay_time) + ' minutes.')

            remove_supernatant(vol, park=park)

    # Protocol Steps 1.2.2 - 1.2.12
    tc.open_lid()
    tc.set_block_temperature(4)
    ctx.pause('Load RNA sample')
    add_beads(120, beads)
    wash(100, RNA_buffer, resuspend=False)
    ctx.delay(minutes=2)
    wash(100, RNA_buffer, resuspend=True)
    wash(50, RNA_buffer, resuspend=True, discard_supernatant=False)
    m300.transfer(50, magplate.columns()[0:num_cols], rnaplate.columns()[0:num_cols], mix_before=(6,40), mix_after=(6,45),
                  air_gap=10)
    tc.close_lid()
    tc.set_lid_temperature(75)
    tc.set_block_temperature(65, hold_time_minutes=5, block_max_volume=50)
    tc.set_block_temperature(4)
    tc.open_lid()





