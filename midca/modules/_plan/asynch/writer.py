from lxml import etree

def write_to_xml(file_name, exp_name, domain, tracks, group, init):
    
    # create helper function for inserting children    
    def insert_child(name, parent=None, text=None):
        elem = etree.Element(name)
        if text is not None:
            elem.text = text

        if parent is not None:
            parent.insert(len(parent), elem)

        return elem


    gctml = etree.Element("gctml")
    
    # fill child elements for expname
    insert_child("expname", gctml, exp_name)


    # fill child elements for domain
    domain_xml = insert_child("domain", gctml)
    rectangle = insert_child("rectangle", domain_xml)
    r_x = insert_child("x", rectangle)
    insert_child("units", r_x, "deg")
    insert_child("value", r_x, domain[0])

    r_y = insert_child("y", rectangle)
    insert_child("units", r_y, "deg")
    insert_child("value", r_y, domain[1])

    r_a = insert_child("a", rectangle)
    insert_child("units", r_a, "met")
    insert_child("value", r_a, domain[2])

    r_b = insert_child("b", rectangle)
    insert_child("units", r_b, "met")
    insert_child("value", r_b, domain[3])

    r_ori = insert_child("ori", rectangle)
    insert_child("units", r_ori, "rad")
    insert_child("value", r_ori, domain[4])


    # fill child elements for tracks
    tracks_xml = insert_child("tracks", gctml)
    point = insert_child("point", tracks_xml)
    insert_child("name", point, "track1")

    t_x = insert_child("x", point)
    insert_child("units", t_x, "deg")
    insert_child("value", t_x, tracks[0])

    t_y = insert_child("y", point)
    insert_child("units", t_y, "deg")
    insert_child("value", t_y, tracks[1])

    t_a = insert_child("a", point)
    insert_child("units", t_a, "met")
    insert_child("value", t_a, tracks[2])

    t_b = insert_child("b", point)
    insert_child("units", t_b, "met")
    insert_child("value", t_b, tracks[3])

    t_p = insert_child("p", point)
    insert_child("value", t_p, tracks[4])

    t_ori = insert_child("ori", point)
    insert_child("units", t_ori, "met")
    insert_child("value", t_ori, tracks[5])


    # fill child elements for group
    group_xml = insert_child("group", gctml)
    glider = insert_child("glider", group_xml)
    insert_child("mnf", glider, group[0])
    insert_child("name", glider, group[1])
    insert_child("sn", glider, group[2])
    if group[3] is not None:
        insert_child("hostname", glider, group[3])
        insert_child("port", glider, group[4])
        insert_child("password", glider, group[5])
        insert_child("gotoname", glider, group[6])

    insert_child("track", glider, "track1")
    insert_child("direction", glider, group[7])
    
    phase = insert_child("phase", glider)
    insert_child("value", phase, group[8])
    insert_child("units", phase, "pct")
    insert_child("opt", phase, "no")


    # fill child elements for init
    insert_child("control", glider, init[0])
    g_x = insert_child("x", glider)
    insert_child("units", g_x, "deg")
    insert_child("value", g_x, init[1])

    g_y = insert_child("y", glider)
    insert_child("units", g_y, "deg")
    insert_child("value", g_y, init[2])

    insert_child("date", glider, init[3])
    insert_child("spd_factor", glider, init[4])

    # write out
    myfile = open(file_name, "w")
    myfile.write(etree.tostring(gctml, xml_declaration=True, pretty_print=True))
    print("Wrote gplan file to " + file_name)



# example (input must all be strings)
file_name = "test.xml"
exp_name = "GR2018"

# (x, y, a, b, ori)
domain = ("-80.9", "30.95", "70e3", "110e3", "-22.288617667674969879954005591571/180*pi")

# (x, y, a, b, p, ori)
tracks = ("-80.868", "31.400", "0", "0", "0", "0")

# (mnf, name, sn, hostname, port, password, gotoname, direction, phase)
group = ("Webb", "franklin", "0", None, None, None, None, "1", "0")

# (control, x, y, date, spd_factor)
init = ("virtual_mooring", "-80.16", "31.07", "2019-10-10 00:00:00", "1")

# test the writer
write_to_xml(file_name, exp_name, domain, tracks, group, init)
