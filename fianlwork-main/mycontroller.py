#!/usr/bin/env python3
import argparse
import os
import sys
from time import sleep

import grpc

# Import P4Runtime lib from parent utils dir
# Probably there's a better way of doing this.
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '../../utils/'))
import p4runtime_lib.bmv2
import p4runtime_lib.helper
from p4runtime_lib.switch import ShutdownAllSwitchConnections

SWITCH_TO_HOST_PORT = 1
SWITCH_TO_SWITCH_PORT = 2


def writeTunnelRules(p4info_helper, ingress_sw,port,len,
                     dst_eth_addr, dst_ip_addr):
    
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ipv4_lpm",
        match_fields={
            "hdr.ipv4.dstAddr": (dst_ip_addr, len)
        },
        action_name="MyIngress.ipv4_forward",
        action_params={
            "dstAddr": dst_eth_addr,
            "port":port
        })
    ingress_sw.WriteTableEntry(table_entry)
   
def ecmp_group(p4info_helper, sw,dst_ip_addr,ecmp_base,ecmp_count):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ecmp_group",
        match_fields={
            "hdr.ipv4.dstAddr": (dst_ip_addr, 32)
        },
        action_name="MyIngress.set_ecmp_select",
        action_params={
            "ecmp_base": ecmp_base,
            "ecmp_count": ecmp_count
        })
    sw.WriteTableEntry(table_entry)

def ecmp_nhop(p4info_helper, sw,ecmp_select,nhop_dmac,nhop_ipv4,port):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ecmp_nhop",
        match_fields={
            "meta.ecmp_select": ecmp_select
        },
        action_name="MyIngress.set_nhop",
        action_params={
            "nhop_dmac": nhop_dmac,
            "nhop_ipv4": nhop_ipv4,
	        "port" : port
        })
    sw.WriteTableEntry(table_entry)

def ecmp_nhop1(p4info_helper, sw,ecmp_select,nhop_dmac,nhop_ipv4,port):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ecmp_nhop1",
        match_fields={
            "meta.ecmp_select": ecmp_select
        },
        action_name="MyIngress.set_nhop",
        action_params={
            "nhop_dmac": nhop_dmac,
            "nhop_ipv4": nhop_ipv4,
	        "port" : port
        })
    sw.WriteTableEntry(table_entry)

def send_frame(p4info_helper, sw,egress_port,smac):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyEgress.send_frame",
        match_fields={
            "standard_metadata.egress_port": egress_port
        },
        action_name="MyEgress.rewrite_mac",
        action_params={
            "smac": smac
        })
    sw.WriteTableEntry(table_entry)


def readTableRules(p4info_helper, sw):
    """
    Reads the table entries from all tables on the switch.

    :param p4info_helper: the P4Info helper
    :param sw: the switch connection
    """
    print('\n----- Reading tables rules for %s -----' % sw.name)
    for response in sw.ReadTableEntries():
        for entity in response.entities:
            entry = entity.table_entry
            # TODO For extra credit, you can use the p4info_helper to translate
            #      the IDs in the entry to names
            table_name = p4info_helper.get_tables_name(entry.table_id)
            print('%s: ' % table_name, end=' ')
            for m in entry.match:
                print(p4info_helper.get_match_field_name(table_name, m.field_id), end=' ')
                print('%r' % (p4info_helper.get_match_field_value(m),), end=' ')
            action = entry.action.action
            action_name = p4info_helper.get_actions_name(action.action_id)
            print('->', action_name, end=' ')
            for p in action.params:
                print(p4info_helper.get_action_param_name(action_name, p.param_id), end=' ')
                print('%r' % p.value, end=' ')
            print()



def printGrpcError(e):
    print("gRPC Error:", e.details(), end=' ')
    status_code = e.code()
    print("(%s)" % status_code.name, end=' ')
    traceback = sys.exc_info()[2]
    print("[%s:%d]" % (traceback.tb_frame.f_code.co_filename, traceback.tb_lineno))

def main(p4info_file_path, bmv2_file_path):
    # Instantiate a P4Runtime helper from the p4info file
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)

    try:
        # Create a switch connection object for s1 and s2;
        # this is backed by a P4Runtime gRPC connection.
        # Also, dump all P4Runtime messages sent to switch to given txt files.
        s1 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s1',
            address='127.0.0.1:50051',
            device_id=0,
            proto_dump_file='logs/s1-p4runtime-requests.txt')
        s2 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s2',
            address='127.0.0.1:50052',
            device_id=1,
            proto_dump_file='logs/s2-p4runtime-requests.txt')

        s3 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s3',
            address='127.0.0.1:50053',
            device_id=2,
            proto_dump_file='logs/s3-p4runtime-requests.txt')
        s4 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s4',
            address='127.0.0.1:50054',
            device_id=3,
            proto_dump_file='logs/s4-p4runtime-requests.txt')
        s5 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s5',
            address='127.0.0.1:50055',
            device_id=4,
            proto_dump_file='logs/s5-p4runtime-requests.txt')
        s6 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s6',
            address='127.0.0.1:50056',
            device_id=5,
            proto_dump_file='logs/s6-p4runtime-requests.txt')
        


        # Send master arbitration update message to establish this controller as
        # master (required by P4Runtime before performing any other write operation)
        s1.MasterArbitrationUpdate()
        s2.MasterArbitrationUpdate()
        s3.MasterArbitrationUpdate()
        s4.MasterArbitrationUpdate()
        s5.MasterArbitrationUpdate()
        s6.MasterArbitrationUpdate()
        # Install the P4 program on the switches
        s1.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s1")
        s2.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s2")

        s3.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s3")

        s4.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s4")
        s5.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s5")

        s6.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s6")

        ecmp_group(p4info_helper,sw=s1,dst_ip_addr="10.0.0.1",ecmp_base=0,ecmp_count=5)
        ecmp_nhop(p4info_helper,sw=s1,ecmp_select=0,nhop_dmac="00:00:00:00:01:02",nhop_ipv4="10.0.2.2",port=2)
        ecmp_nhop(p4info_helper,sw=s1,ecmp_select=1,nhop_dmac="00:00:00:00:01:03",nhop_ipv4="10.0.3.3",port=3)
        ecmp_nhop1(p4info_helper,sw=s1,ecmp_select=2,nhop_dmac="00:00:00:00:01:04",nhop_ipv4="10.0.4.4",port=4)
        ecmp_nhop1(p4info_helper,sw=s1,ecmp_select=3,nhop_dmac="00:00:00:00:01:05",nhop_ipv4="10.0.5.5",port=5)
        ecmp_nhop1(p4info_helper,sw=s1,ecmp_select=4,nhop_dmac="00:00:00:00:01:05",nhop_ipv4="10.0.5.5",port=5)
        send_frame(p4info_helper,sw=s1,egress_port=2,smac="00:00:00:01:02:00")
        send_frame(p4info_helper,sw=s1,egress_port=3,smac="00:00:00:01:03:00")
        send_frame(p4info_helper,sw=s1,egress_port=4,smac="00:00:00:01:04:00")
        send_frame(p4info_helper,sw=s1,egress_port=5,smac="00:00:00:01:05:00")

        ecmp_group(p4info_helper,sw=s2,dst_ip_addr="10.0.0.1",ecmp_base=0,ecmp_count=1)
        ecmp_nhop(p4info_helper,sw=s2,ecmp_select=0,nhop_dmac="08:00:00:00:02:02",nhop_ipv4="10.0.2.2",port=2)
        send_frame(p4info_helper,sw=s2,egress_port=2,smac="00:00:00:02:01:00")
        
        ecmp_group(p4info_helper,sw=s3,dst_ip_addr="10.0.0.1",ecmp_base=0,ecmp_count=1)
        ecmp_nhop(p4info_helper,sw=s3,ecmp_select=0,nhop_dmac="08:00:00:00:02:02",nhop_ipv4="10.0.2.2",port=2)
        send_frame(p4info_helper,sw=s3,egress_port=2,smac="00:00:00:02:01:00")

        ecmp_group(p4info_helper,sw=s4,dst_ip_addr="10.0.0.1",ecmp_base=0,ecmp_count=1)
        ecmp_nhop(p4info_helper,sw=s4,ecmp_select=0,nhop_dmac="08:00:00:00:02:02",nhop_ipv4="10.0.2.2",port=2)
        send_frame(p4info_helper,sw=s4,egress_port=2,smac="00:00:00:02:01:00")

        ecmp_group(p4info_helper,sw=s5,dst_ip_addr="10.0.0.1",ecmp_base=0,ecmp_count=1)
        ecmp_nhop(p4info_helper,sw=s5,ecmp_select=0,nhop_dmac="08:00:00:00:02:02",nhop_ipv4="10.0.2.2",port=2)
        send_frame(p4info_helper,sw=s5,egress_port=2,smac="00:00:00:02:01:00")

        ecmp_group(p4info_helper,sw=s6,dst_ip_addr="10.0.0.1",ecmp_base=0,ecmp_count=1)
        ecmp_nhop(p4info_helper,sw=s6,ecmp_select=0,nhop_dmac="08:00:00:00:02:02",nhop_ipv4="10.0.2.2",port=1)
        send_frame(p4info_helper,sw=s6,egress_port=1,smac="00:00:00:02:01:00")

        # TODO Uncomment the following two lines to read table entries from s1 and s2
        readTableRules(p4info_helper, s1)
        readTableRules(p4info_helper, s2)
        readTableRules(p4info_helper, s3)   
        readTableRules(p4info_helper, s4)
        readTableRules(p4info_helper, s5)
        readTableRules(p4info_helper, s6)   

            

    except KeyboardInterrupt:
        print(" Shutting down.")
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='./build/load_balance.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='./build/load_balance.json')
    args = parser.parse_args()

    if not os.path.exists(args.p4info):
        parser.print_help()
        print("\np4info file not found: %s\nHave you run 'make'?" % args.p4info)
        parser.exit(1)
    if not os.path.exists(args.bmv2_json):
        parser.print_help()
        print("\nBMv2 JSON file not found: %s\nHave you run 'make'?" % args.bmv2_json)
        parser.exit(1)
    main(args.p4info, args.bmv2_json)
