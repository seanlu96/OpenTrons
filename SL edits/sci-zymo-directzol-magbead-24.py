# Link to protocol https://protocols.opentrons.com/protocol/sci-zymo-directzol-magbead

# Importing values from website
# Samples = 8
# Deepwell Type = usascientific_96_wellplate_2.4ml_deep
# Reservoir Type = Nest 12 reservoir 15ml
# Starting Volume = 200ml
# Park Tips = True
# mag gen = Magnetic module gen 2
# m300_mount = left
# biorad_96_wellplate_200ul_pcr
# usascientific_96_wellplate_2.4ml_deep

def get_values(*names):
    import json
    _all_values = json.loads("""{"num_samples":8,"deepwell_type":"usascientific_96_wellplate_2.4ml_deep",
    "res_type":"nest_12_reservoir_15ml","starting_vol":500,"elution_vol":50,"park_tips":false,
    "mag_gen":"magnetic module gen2","m300_mount":"left"}""")
    return [_all_values[n] for n in names]


from opentrons.types import Point
import json
import os
import math
from opentrons import types


metadata = {
    'protocolName': 'Zymo Research Direct-zol™-96 MagBead RNA Kit',
    'author': 'Opentrons <protocols@opentrons.com>',
    'apiLevel': '2.8'
}


# Start protocol
def run(ctx):

    ctx.set_rail_lights(True)

    [num_samples, deepwell_type, res_type, starting_vol,
     elution_vol, park_tips, mag_gen, m300_mount] = get_values(  # noqa: F821
        'num_samples', 'deepwell_type', 'res_type', 'starting_vol',
        'elution_vol', 'park_tips', 'mag_gen', 'm300_mount')

    if num_samples % 8 != 0:
        raise Exception("Enter a sample number wholly divisible by 8")
    if not 0 <= num_samples <= 24:
        raise Exception("Enter a sample number between 1-24")

    if mag_gen == 'magdeck':
        MAG_HEIGHT = 13.6
    elif mag_gen == 'magnetic module gen2':
        MAG_HEIGHT = 6.5
    else:
        MAG_HEIGHT = 6.8


    settling_time = 5 #TODO: optomize?

    """
    Here is where you can change the locations of your labware and modules
    (note that this is the recommended configuration)
    """
    magdeck = ctx.load_module(mag_gen, '4')
    magdeck.disengage()
    magplate = magdeck.load_labware(deepwell_type, 'deepwell plate')
    tc = ctx.load_module('thermocycler')
    elutionplate = tc.load_labware('biorad_96_wellplate_200ul_pcr')
    #tempdeck = ctx.load_module('temperature module gen2', '3')
    #tapestation_tubes = tempdeck.load_labware('opentrons_96_aluminumblock_biorad_wellplate_200ul') #actually tapestation tube, not plate
    waste = ctx.load_labware('nest_1_reservoir_195ml', '9',
                             'Liquid Waste').wells()[0].top()
    res1 = ctx.load_labware(res_type, '5', 'reagent reservoir 1')
    num_cols = math.ceil(num_samples/8)
    tips300 = [ctx.load_labware('opentrons_96_tiprack_300ul', slot,
                                '200µl filtertiprack')
               for slot in ['2', '3', '6']]
    if park_tips:
        parkingrack = ctx.load_labware(
            'opentrons_96_tiprack_300ul', '1', 'tiprack for parking')
        parking_spots = parkingrack.rows()[0][:num_cols]
    else:
        tips300.insert(0, ctx.load_labware('opentrons_96_tiprack_300ul', '1',
                                           '200µl filtertiprack'))
        parking_spots = [None for none in range(12)]

    # load P300M pipette
    m300 = ctx.load_instrument(
        'p300_multi_gen2', m300_mount, tip_racks=tips300)

    tip_log = {val: {} for val in ctx.loaded_instruments.values()}
    """
    Here is where you can define the locations of your reagents.
    """

    binding_buffer = res1.wells()[0]
    wash1 = res1.wells()[1]
    wash2 = res1.wells()[2]
    dnase1 = res1.wells()[3]
    stopreaction = res1.wells()[4]
    wash3 = res1.wells()[5]
    elution_solution = res1.wells()[7]
    wash4 = res1.wells()[6]

    mag_samples_m = magplate.rows()[0][:num_cols]
    elution_samples_m = elutionplate.rows()[0][:num_cols]

    #magdeck.disengage()  # just in case
    #tempdeck.set_temperature(4)

    m300.flow_rate.aspirate = 50
    m300.flow_rate.dispense = 150
    m300.flow_rate.blow_out = 300
    tip_track = False #Track tips on pipette

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
    drop_threshold = 193 #Was 120

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

    waste_vol = 0
    waste_threshold = 185000

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
                ctx.set_rail_lights(False)
                ctx.pause('Please empty liquid waste (slot 11) before \
                resuming.')
                ctx.set_rail_lights(True)
                ctx.home()  # home before continuing with protocol
                waste_vol = 0
            waste_vol += vol

        m300.flow_rate.aspirate = 30
        num_trans = math.ceil(vol/200)
        vol_per_trans = vol/num_trans
        for i, (m, spot) in enumerate(zip(mag_samples_m, parking_spots)):
            if park:
                _pick_up(m300, spot)
            else:
                _pick_up(m300)
            side = -1 if i % 2 == 0 else 1
            loc = m.bottom(0.5).move(Point(x=side*2))
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
                pip.aspirate(mix_vol, center, rate=2.0)
                pip.dispense(mix_vol, top[rightLeft], rate=2.0)
            for _ in range(2):
                pip.aspirate(mix_vol, center, rate=2.0)
                pip.dispense(mix_vol, bottom[rightLeft], rate=2.0)

    def bind(vol, park=True):
        """
        `bind` will perform magnetic bead binding on each sample in the
        deepwell plate. Each channel of binding beads will be mixed before
        transfer, and the samples will be mixed with the binding beads after
        the transfer. The magnetic deck activates after the addition to all
        samples, and the supernatant is removed after bead binding.
        :param vol (float): The amount of volume to aspirate from the elution
                            buffer source and dispense to each well containing
                            beads.
        :param park (boolean): Whether to save sample-corresponding tips
                               between adding elution buffer and transferring
                               supernatant to the final clean elutions PCR
                               plate.
        """
        latest_chan = -1
        for i, (well, spot) in enumerate(zip(mag_samples_m, parking_spots)):
            _pick_up(m300)
            num_trans = math.ceil(vol/200)
            vol_per_trans = vol/num_trans
            asp_per_chan = (0.95*res1.wells()[0].max_volume)//(vol_per_trans*8)
            for t in range(num_trans):
                chan_ind = int((i*num_trans + t)//asp_per_chan)
                if two_res:
                    source = binding_buffer[chan_ind]
                else:
                    source = binding_buffer
                if m300.current_volume > 0:
                    # void air gap if necessary
                    m300.dispense(m300.current_volume, source.top())
                if chan_ind > latest_chan:  # mix if accessing new channel
                    for _ in range(11):
                        m300.aspirate(180, source.bottom(0.5), rate=2)
                        m300.dispense(180, source.bottom(5), rate=2)
                    latest_chan = chan_ind
                m300.transfer(vol_per_trans, source, well.top(), air_gap=20,
                              new_tip='never')
                if t < num_trans - 1:
                    m300.air_gap(20)
            m300.mix(5, 200, well)
            m300.blow_out(well.top(-2))
            m300.touch_tip()
            m300.air_gap(20)
            if park:
                m300.drop_tip(spot)
            else:
                _drop(m300)
        ctx.set_rail_lights(False)
        # Mix using pipettes
        for _ in range(5):
            for i, (well, spot) in enumerate(zip(mag_samples_m, parking_spots)):
                _pick_up(m300)
                m300.mix(6, 200, well)
                m300.blow_out()
                m300.touch_tip()
                _drop(m300)
            ctx.delay(minutes=1)
        magdeck.engage(height=MAG_HEIGHT)
        ctx.delay(minutes=settling_time, msg='Incubating on MagDeck for \
' + str(settling_time) + ' minutes.')

        # remove initial supernatant
        remove_supernatant(vol+starting_vol, park=park)

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
            if two_res:
                src = source[i//(12//len(source))]
            else:
                src = source
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

    def dnase(vol, source, mix_reps=6, park=True, resuspend=True):

        if resuspend and magdeck.status == 'engaged':
            magdeck.disengage()

        num_trans = math.ceil(vol/200)
        vol_per_trans = vol/num_trans
        for i, (m, spot) in enumerate(zip(mag_samples_m, parking_spots)):
            #_pick_up(m300)
            # side = 1 if i % 2 == 0 else -1
            # loc = m.bottom(0.5).move(Point(x=side*2))
            # if two_res:
            #     src = source[i//(12//len(source))]
            # else:
            #     src = source
            # for n in range(num_trans):
            #     if m300.current_volume > 0:
            #         m300.dispense(m300.current_volume, src.top())
            #     m300.transfer(vol_per_trans, src, m.top(), air_gap=20,
            #                   new_tip='never')
            #     if n < num_trans - 1:  # only air_gap if going back to source
            #         m300.air_gap(20)
            # if resuspend:
            #     # m300.mix(mix_reps, 30, loc)
            #     resuspend_pellet(m, m300, 50)
            # m300.mix(mix_reps, 30)
            # m300.blow_out(m.top())
            # m300.air_gap(20)
            #if park:
            #    m300.drop_tip(spot)
            #else:
            #    _drop(m300)
        #TODO: Fix not enough volume in well to allow for multichannel, for now it is by hand
        ctx.pause('Add DNase by hand')

        #Incubate 10 min, mix 3 times
        delay_sec = float(300 - (num_samples / 8) * 25)
        ctx.delay(seconds=delay_sec)
        for i, (m, spot) in enumerate(zip(mag_samples_m, parking_spots)):
            _pick_up(m300, spot)
            m300.mix(mix_reps, 0.9*vol, m.bottom(0.5))
            m300.blow_out(m.top(-2))
            m300.touch_tip()
            _drop(m300)

        ctx.delay(seconds = delay_sec)

        for i, (m, spot) in enumerate(zip(mag_samples_m, parking_spots)):
            _pick_up(m300, spot)
            m300.mix(mix_reps, 0.9*vol, m.bottom(0.5))
            m300.blow_out(m.top(-2))
            m300.touch_tip()
            _drop(m300)


    def stop_reaction(vol, source, mix_reps=6, park=True, resuspend=True):

        if resuspend and magdeck.status == 'engaged':
            magdeck.disengage()

        num_trans = math.ceil(vol/200)
        vol_per_trans = vol/num_trans
        for i, (m, spot) in enumerate(zip(mag_samples_m, parking_spots)):
            _pick_up(m300)
            # side = 1 if i % 2 == 0 else -1
            # loc = m.bottom(0.5).move(Point(x=side*2))
            if two_res:
                src = source[i//(12//len(source))]
            else:
                src = source
            for n in range(num_trans):
                if m300.current_volume > 0:
                    m300.dispense(m300.current_volume, src.top())
                m300.transfer(vol_per_trans, src, m.top(), air_gap=20,
                              new_tip='never')
                if n < num_trans - 1:  # only air_gap if going back to source
                    m300.air_gap(20)
            if resuspend:
                # m300.mix(mix_reps, 50, loc)
                resuspend_pellet(m, m300, 180)
            m300.blow_out(m.top())
            m300.air_gap(20)
            if park:
                m300.drop_tip(spot)
            else:
                _drop(m300)

        #Incubate 10 min, mix 3 times
        if 0.9*vol < 200:
            mix_vol = 0.9*vol
        else:
            mix_vol = 100

        delay_sec = float(300 - (num_samples / 8) * 25)
        ctx.delay(seconds=delay_sec)

        for i, (m, spot) in enumerate(zip(mag_samples_m, parking_spots)):
            _pick_up(m300, spot)
            m300.mix(mix_reps, mix_vol, m.bottom(0.5))
            m300.blow_out(m.top(-2))
            m300.drop_tip(spot)

        ctx.delay(seconds=delay_sec)

        for i, (m, spot) in enumerate(zip(mag_samples_m, parking_spots)):
            _pick_up(m300, spot)
            m300.mix(mix_reps, mix_vol, m.bottom(0.5))
            m300.blow_out(m.top(-2))
            m300.drop_tip(spot)

        if magdeck.status == 'disengaged':
            magdeck.engage(height=MAG_HEIGHT)

        ctx.delay(minutes=settling_time, msg='Incubating on MagDeck for ' + str(settling_time) + ' minutes.')

        remove_supernatant(vol+50, park=park)

    def elute(vol, park=True):
        """
        `elute` will perform elution from the deepwell extraciton plate to the
        final clean elutions PCR plate to complete the extraction protocol.
        :param vol (float): The amount of volume to aspirate from the elution
                            buffer source and dispense to each well containing
                            beads.
        :param park (boolean): Whether to save sample-corresponding tips
                               between adding elution buffer and transferring
                               supernatant to the final clean elutions PCR
                               plate.
        """

        # resuspend beads in elution
        magdeck.disengage()
        for i, (m, spot) in enumerate(zip(mag_samples_m, parking_spots)):
            _pick_up(m300)
            side = 1 if i % 2 == 0 else -1
            loc = m.bottom(0.5).move(Point(x=side*2))
            m300.aspirate(vol, elution_solution)
            m300.move_to(m.center())
            m300.dispense(vol, loc)
            # m300.mix(mix_reps, 0.8*vol, loc)
            resuspend_pellet(m, m300, 50)
            m300.blow_out(m.bottom(5))
            m300.air_gap(20)
            if park:
                m300.drop_tip(spot)
            else:
                _drop(m300)

        magdeck.engage(height=MAG_HEIGHT)
        ctx.delay(minutes=settling_time, msg='Incubating on MagDeck for \
' + str(settling_time) + ' minutes.')

        for i, (m, e, spot) in enumerate(
                zip(mag_samples_m, elution_samples_m, parking_spots)):
            side = -1 if i % 2 == 0 else 1
            loc = m.bottom(0.5).move(Point(x=side * 2))
            if park:
                _pick_up(m300, spot)
                m300.transfer(vol, loc, e.bottom(5), air_gap=20, new_tip='never')
                m300.blow_out(e.top(-2))
                m300.air_gap(20)
                m300.drop_tip()
            else:
                m20.transfer(vol, loc, e.bottom(5), air_gap=2, new_tip='always', blow_out=True)

    def tapestation_aliquots(vol):
        for i, (e, t) in enumerate(zip(elution_samples_m, tapestation_tubes_m)):
            m20.transfer(vol, e, t)

    """
    Here is where you can call the methods defined above to fit your specific
    protocol. The normal sequence is:
    """
    bind(420, park=park_tips)
    ctx.comment('\n\n\n')
    wash(500, wash1, park=park_tips)
    ctx.comment('\n\n\n')
    wash(500, wash2, park=park_tips)
    ctx.comment('\n\n\n')
    wash(500, wash3, park=park_tips)
    ctx.comment('\n\n\n')
    wash(300, wash4, park=park_tips)
    ctx.comment('\n\n\n')
    # dnase1 treatment
    dnase(50, dnase1, park=park_tips)
    ctx.comment('\n\n\n')
    stop_reaction(500, stopreaction, park=park_tips)
    ctx.comment('\n\n\n')
    ctx.delay(minutes=5, msg="dry beads for 10 minute (5 min + tc set temperature)")
    tc.set_block_temperature(4)
    elute(elution_vol, park=False)

    # track final used tip
    if tip_track and not ctx.is_simulating():
        if not os.path.isdir(folder_path):
            os.mkdir(folder_path)
        data = {pip.name: tip_log[pip]['count'] for pip in tip_log}
        with open(tip_file_path, 'w') as outfile:
            json.dump(data, outfile)