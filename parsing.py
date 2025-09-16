from __future__ import print_function
import copy

from numpy import isin
from pycrate_asn1dir import S1AP
import pycrate_mobile.NAS
import sys
import json
from IMSI import IMSI as IMSI
from lte_cause import *
# see attach reject commentary



TAU_NOT_ALLOWED = b'\x0C' # 12 
NO_SUITABLE_CELL = b'\x0F' # 15 force the UE to search another TAU
EPS_NOT_ALLOWED = b'\x07' # 7 no EPS switch to 2G
EPS_NONEPS_NOT_ALLOWED = b'\x08' # 8 This EMM cause is sent to the UE when it is not allowed to operate either EPS or non-EPS services. DOS
UE_ID_NOT_DERIVED = b'\x09' # This EMM cause is sent to the UE when the network cannot derive the UE’s identity from the GUTI/S-TMSI/P-TMSI and RAI 
 #e.g. no matching identity/context in the network or failure to validate the UE’s identity due to integrity check failure of the received message.
IMPLICITLY_DETACHED = b'\x0A' # implicitly detach ( used to force reconnect phone 

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


############################################################################################

class parsing:
    IMSI_list = []
    cause_TAUreject = LIBLTE_MME_EMM_CAUSE_UE_IDENTITY_CANNOT_BE_DERIVED_BY_THE_NETWORK #msg used to force mobile to provide its imsi
    def checkIE_accepted(self,protocolIEs_list: dict, list_of_mandatory_IEs: dict, list_of_optional_IEs: dict) -> bool:
        """check if all Mandatory IEs are present"""
        mandatory_IEs_and_their_presence = copy.deepcopy(list_of_mandatory_IEs)
        optional_IEs_and_their_presence = copy.deepcopy(list_of_optional_IEs)
        for IE in protocolIEs_list:
            try:
                id = IE['id']
                criticality = IE['criticality']
            except (KeyError, ValueError,TypeError):
                eprint("error reading parameters that should be there per library. Fatal error, exiting..")
                exit()
            tmpIE = (id, criticality)

            if tmpIE in list_of_mandatory_IEs:
                if tmpIE in mandatory_IEs_and_their_presence:
                    mandatory_IEs_and_their_presence.remove(tmpIE)
                else:
                    eprint("mandatory IE was there twice")
                    return False
            elif tmpIE in list_of_optional_IEs:
                if tmpIE in optional_IEs_and_their_presence:
                    optional_IEs_and_their_presence.remove(tmpIE)
                else:
                    eprint("optional IE was there twice")
                    return False
            else:
                eprint("unknown IE: ", tmpIE)
                return False
        if mandatory_IEs_and_their_presence:
            eprint("not all Mandatory IEs present")
            return False
        return True

    def S1SetupRequest(self,EPC_server, protocolIEs_list):
        """Parse a S1 Setup request and establish a connection """
        print('S1SetupRequest')
        list_of_mandatory_IEs = [
            (59, 'reject'),
            (64, 'reject'),
            (137, 'ignore'),
        ]
        list_of_optional_IEs = [
            (60, 'ignore'),
            (232, 'reject'),
            (228, 'ignore'),
            (127, 'reject'),
            (234, 'ignore'),
        ]
        #tmp = parsing.checkIE_accepted(
        #    protocolIEs_list, list_of_mandatory_IEs, list_of_optional_IEs)
        tmp = self.checkIE_accepted(
            protocolIEs_list, list_of_mandatory_IEs, list_of_optional_IEs)
        
        for i in protocolIEs_list:
            id = i['id']
            criticality = i['criticality']
            value = i['value'][1]
            
            #print('id',id)
            #print(criticality)
            #print(value)
            if id == 59:
                # Initialize the result to 0
                result = 0

                # Iterate over the bytes in the value, starting from the right
                for i, byte in enumerate((value['pLMNidentity'])):
                    # Swap the upper and lower nibbles of the byte
                    swapped_byte = ((byte & 0x0f) << 4) | ((byte & 0xf0) >> 4)

                    # Convert the swapped byte to its decimal representation
                    decimal_value = swapped_byte

                    # Multiply the decimal value by 10 to the power of i
                    result += decimal_value * (10 ** i)


                print(result)
                print(value['pLMNidentity'])
                print(value['eNB-ID'])
        return True

    def S1SetupResponse(self,epcServer,fd, success):
        """
        Creates and sends a S1SetupResponse or S1SetupFailure
        """
        if success:
            IEs = []
            # plmn to be adapted
            IEs.append({'id': 105, 'criticality': 'reject', 'value': ('ServedGUMMEIs', [{'servedPLMNs': [
                       b'\x02\xf6\x01'], 'servedGroupIDs': [b'\x01\x00'], 'servedMMECs': [b'\x1a']}])})
            IEs.append({'id': 87, 'criticality': 'ignore',
                       'value': ('RelativeMMECapacity', 255)})
            val = ('successfulOutcome', {'procedureCode': 17, 'criticality': 'ignore', 'value': (
                'S1SetupResponse', {'protocolIEs': IEs})})
            epcServer.encode_and_send_packet(val,fd)
        else:  # failed
            print("failed s1setup response ")
            IEs = []
            # cause
            IEs.append({'id': 2, 'criticality': 'ignore',
                       'value': ('Cause', ('misc', 'unspecified'))})
            val = ('unsuccessfulOutcome', {'procedureCode': 17, 'criticality': 'ignore', 'value': (
                'S1SetupFailure', {'protocolIEs': IEs})})
            epcServer.encode_and_send_packet(val,fd)
    def UplinkNASTransport(self,epcServer, fd,protocolIEs_list):
        print('UplinkNASTransport')
        list_of_mandatory_IEs = [
            (0,'reject'),
            (8, 'reject'),
            (26, 'reject'),
            (100, 'ignore'),
            (67, 'ignore'),
        ]
        list_of_optional_IEs = [ 
            (155, 'ignore'),
            (184, 'ignore'),
            (186, 'ignore'),
        ]
        #if not parsing.checkIE_accepted(protocolIEs_list, list_of_mandatory_IEs, list_of_optional_IEs):
        if not self.checkIE_accepted(protocolIEs_list, list_of_mandatory_IEs, list_of_optional_IEs):
            eprint("invalid message, skipping it")
        enb_ue_id = None
        for i in protocolIEs_list:
            id = i['id']
            criticality = i['criticality']
            value = i['value']
            if id == 8:
                enb_ue_id = value[1]
            if id == 26:
                value = value[1]  # discard text description
                msg, err = pycrate_mobile.NAS.parse_NAS_MO(value)  # MobileOriginating decode
                if err:
                    raise Exception("Decoding of incoming MO failed")
                elif type(msg).__name__ == 'EMMSecProtNASMessage':
                    with open("UplinkNASTransport.json", "a") as write_file:
                        #json.dump(msg.to_json(), write_file)
                        write_file.write(msg.to_json())
                    if any(isinstance(item, pycrate_mobile.NAS.EMMIdentityResponse) for item in msg):
                        print('got identity response 2')
                        # for i in msg:
                        #     print(i)
                        # exit()
                        ident_type, code = msg['EMMIdentityResponse']['ID'][1].decode()
                        if ident_type == 1:
                            print('imsi 2 is',code)
                            #epcServer.write_imsi(code)
                            with open(f"EMMAttachRequest_{code}.json", "a") as write_file:
                                #json.dump(msg.to_json(), write_file)
                                write_file.write(msg.to_json())
                            #parsing.append_imsi(code)
                            #parsing.decide_attach(epcServer,code,enb_ue_id)
                            epcServer.write_imsi(code, "EMMIdentityResponse", msg.to_json())
                            self.append_imsi(code)
                            # Call this function whenever new data arrives
                            #update_epc_data(code, "'EMMIdentityResponse", msg.to_json())
                            self.decide_attach(epcServer,fd,code,enb_ue_id)
                elif type(msg).__name__ == 'EMMIdentityResponse':
                    print (" got direct identity response")
                    print(type(msg))
                    print(msg)
                    #if any(isinstance(item, pycrate_mobile.TS24301_EMM.EMMIdentityResponse) for item in msg):
                    #for item in msg :
                        #print(item)
                    ident_type, code = msg['ID'][1].decode()
                    print(code)
                    epcServer.write_imsi(code, "EMMIdentityResponse", msg.to_json())
                        #ident_type = print(msg['ID'][1].get_val())
                        #code = print(msg['EMMIdentityResponse']['ID'][1]['IMSI'].get_val())
                        #self.append_imsi(code)
                    self.decide_attach(epcServer,fd,code,enb_ue_id)
                elif type(msg).__name__== 'EMMAttachRequest':
                    print ('got direct EMMAttachRequest')
                    self.send_identityRequest(epcServer,fd, enb_ue_id)
                else:
                    
                    print(type(msg))
                    print(msg)
    def decide_attach(self,epcServer,fd,code,enb_ue_id,cause = LIBLTE_MME_EMM_CAUSE_IMPLICITLY_DETACHED):
        '''
        if epcServer.omit != None and code in epcServer.omit:
            #parsing.send_attachReject(epcServer, 111, enb_ue_id)
            #parsing.send_attachReject(epcServer, 111)
            self.send_attachReject(epcServer, fd,111,cause)
        elif epcServer.omit != None and code not in epcServer.omit:
            #parsing.send_attachReject(epcServer, enb_ue_id)
            self.send_attachReject(epcServer, fd,enb_ue_id,cause)
        elif epcServer.target != None and code in epcServer.target:
            print("enb_ue_id : ",enb_ue_id)
            #parsing.send_attachReject(epcServer, enb_ue_id)
            self.send_attachReject(epcServer,fd, enb_ue_id,cause)
        elif epcServer.omit == None and epcServer.target == None:
            #parsing.send_attachReject(epcServer, enb_ue_id)
            self.send_attachReject(epcServer, fd,enb_ue_id,cause)
        '''
        reject = epcServer.Imsi_reject(code)
        if reject is not None:
            cause=reject
        else:
            cause=epcServer.attach_reject_reason
        self.send_attachReject(epcServer, fd,enb_ue_id,cause)

    def UEContextReleaseRequest(self,epcServer,protocolIEs_list):
        """parse ue context release request"""

    def InitialUEMessage(self,epcServer, fd,protocolIEs_list):
        """Parse Initial UE message, and invoke NAS methods"""
        list_of_mandatory_IEs = [
            (8, 'reject'),
            (26, 'reject'),
            (67, 'reject'),
            (100, 'ignore'),
            (134, 'ignore'),
        ]
        list_of_optional_IEs = [
            (96, 'reject'),
            (127, 'reject'),
            (75, 'reject'),
            (145, 'reject'),
            (155, 'ignore'),
            (160, 'reject'),
            (170, 'ignore'),
            (176, 'ignore'),
            (184, 'ignore'),
            (186, 'ignore'),
            (223, 'ignore'),
            (230, 'ignore'),
            (242, 'ignore'),
            (246, 'ignore'),
            (250, 'ignore'),
        ]
        print("in initial UE message parser")
        # if not parsing.checkIE_accepted(protocolIEs_list, list_of_mandatory_IEs, list_of_optional_IEs):
        if not self.checkIE_accepted(protocolIEs_list, list_of_mandatory_IEs, list_of_optional_IEs):
            eprint("invalid message, skipping it")
        enb_ue_id = None
        for i in protocolIEs_list:#go through the list of all IEs (there are already all mandatory IEs)
            #we expect that they come in sorted
            id = i['id']
            criticality = i['criticality']
            value = i['value']
            if id == 8:  # id -eNB-UE-S1AP-ID
                enb_ue_id = value[1]
            if id == 26:  # NAS-PDU message -> encapsualted communication between UE and MME inside IE
                value = value[1]  # discard text description
                msg, err = pycrate_mobile.NAS.parse_NAS_MO(value)  # MobileOriginating decode
                if err:
                    raise Exception("Decoding of incoming MO failed")
                if type(msg).__name__ == 'EMMAttachRequest': # 65
                    print("got Attach Request 1")
                    #print('EEA0 : ',msg['EMMTrackingAreaUpdateRequest']['UENetCap']['UENetCap']['EEA0']._val)
                    #print(msg)
                    
                    #print('epsid : ',msg['EPSID'][1].decode())
                    ident_type = msg['EPSID'][1]['Type'].get_val()
                    #ident_type, code = msg['EPSID'][1].decode()
                    if ident_type == 1:
                        ident_type, code = msg['EPSID'][1].decode()
                        print("imsi is ", code)
                        #epcServer.write_imsi(code)
                        #parsing.append_imsi(code)
                        self.append_imsi(code)
                        epcServer.write_imsi(code, "EMMAttachRequest", msg.to_json())
                        #update_epc_data(code, "'EMMAttachRequest", msg.to_json())
                        with open(f"EMMAttachRequest_{code}.json", "a") as write_file:
                        #json.dump(msg.to_json(), write_file)
                            write_file.write(msg.to_json())
                        #parsing.decide_attach(epcServer,code,enb_ue_id)
                        self.decide_attach(epcServer,fd,code,enb_ue_id)
                    else:
                        print("got here type :",ident_type)
                        with open(f"EMMAttachRequest_noIMSI.json", "a") as write_file:
                        #json.dump(msg.to_json(), write_file)
                            write_file.write(msg.to_json())
                        #parsing.send_identityRequest(epcServer, enb_ue_id)
                        self.send_identityRequest(epcServer,fd, enb_ue_id)
                elif type(msg).__name__ == 'EMMSecProtNASMessage':
                    print("protnas")
                    with open("EMMSecProtNASMessage.json", "a") as write_file:
                        #json.dump(msg.to_json(), write_file)
                        write_file.write(msg.to_json())
                    if any(isinstance(item, pycrate_mobile.NAS.EMMTrackingAreaUpdateRequest) for item in msg): #TAU request
                        print("got TAURequest")
                        #with open("EMMSecProtNASMessage_TAURequest.json", "a") as write_file:
                        #json.dump(msg.to_json(), write_file)
                            # write_file.write(msg.to_json())
                        #parsing.send_TAUReject(epcServer, cause_TAUreject,enb_ue_id)
                        self.send_TAUReject(epcServer, fd,self.cause_TAUreject,enb_ue_id)
                    if any(isinstance(item, pycrate_mobile.NAS.EMMAttachRequest) for item in msg): #attach Request
                        print("got Attach request")
                        ident_type = print(msg['EMMAttachRequest']['EPSID'][1]['Type'].get_val())
                        if ident_type == 1:
                            #ident_type = print(msg['EMMAttachRequest']['EPSID'][1]['IMSI'].get_val())
                            code = print(msg['EMMAttachRequest']['EPSID'][1]['IMSI'].get_val())
                            print("imsi is ", code)
                            #parsing.append_imsi(code)
                            self.append_imsi(code)
                            #epcServer.write_imsi(code)
                            #update_epc_data(code, "EMMSecProtNASMessage", msg.to_json())
                            epcServer.write_imsi(code, "EMMSecProtNASMessage", msg.to_json())
                            #parsing.decide_attach(epcServer,code,enb_ue_id)
                            self.decide_attach(epcServer,fd,code,enb_ue_id)
                        else:
                            print("The identity is not IMSI. Sending Identity Request ..")
                            #parsing.send_identityRequest(epcServer, enb_ue_id)  
                            self.send_identityRequest(epcServer,fd, enb_ue_id)
                    if any(isinstance(item, pycrate_mobile.NAS.EMMIdentityResponse) for item in msg): #attach Request
                        print("got identity response")
                        ident_type = print(msg['EMMIdentityResponse']['EPSID'][1]['Type'].get_val())
                        if ident_type == 1:
                            ident_type = print(msg['EMMIdentityResponse']['EPSID'][1]['IMSI'].get_val())
                            print("imsi is ", code)
                            #epcServer.write_imsi(code)
                            self.append_imsi(code)
                            epcServer.write_imsi(code, "EMMIdentityResponse", msg.to_json())
                            #update_epc_data(code, "'EMMIdentityResponse", msg.to_json())
                            #parsing.decide_attach(epcServer,code,enb_ue_id)
                            self.decide_attach(epcServer,fd,code,enb_ue_id)
                        else:
                            print("The identity is not IMSI. Sending Identity Request ..")
                            #parsing.send_identityRequest(epcServer, enb_ue_id) 
                            self.send_identityRequest(epcServer, fd,enb_ue_id) 
                elif type(msg).__name__ == 'EMMTrackingAreaUpdateRequest':
                    #if any(isinstance(item, pycrate_mobile.NAS.EMMTrackingAreaUpdateRequest) for item in msg): #TAU request
                    print("got direct TAURequest")
                        #with open("EMMSecProtNASMessage_TAURequest.json", "a") as write_file:
                        #json.dump(msg.to_json(), write_file)
                            # write_file.write(msg.to_json())
                        #parsing.send_TAUReject(epcServer, cause_TAUreject,enb_ue_id)
                    #self.send_identityRequest(epcServer, enb_ue_id) 
                    self.send_TAUReject(epcServer, fd,self.cause_TAUreject,enb_ue_id)
                else: 
                    print("instead got type ",type(msg).__name__)
                    with open("unknown.json", "a") as write_file:
                        #json.dump(msg.to_json(), write_file)
                        write_file.write(msg.to_json())
                    
                #print("this is id type and its value: ",msg['EPSID'][0],msg['EPSID'][1])
                # pycrate_mobile.NAS.show(msg._opts)
                # sprint(msg['EPSID']['Type'])

                ########################    N E W   M E S A G G E    ##########################




    ############  D E F I N I T I O N S  ######################################################
    def append_imsi(self,imsi):
        #if imsi not in parsing.IMSI_list:
        #    parsing.IMSI_list.append(imsi)
        #print(parsing.IMSI_list)
        #if imsi not in self.IMSI_list:
        #    self.IMSI_list.append(IMSI(imsi,0))
        if not self.IMSI_list:
            self.IMSI_list.append(IMSI(imsi))
        for idx in self.IMSI_list:
            if idx.imsi != imsi:
                self.IMSI_list.append(IMSI(imsi))
            print(idx.imsi)
        #print(self.IMSI_list)
			
    # TAU NAS
    def create_NAS_only_TAURequest(self):
        return pycrate_mobile.NAS.EMMTrackingAreaUpdateRequest().to_bytes()

    def create_NAS_only_TAUReject(self,cause=LIBLTE_MME_EMM_CAUSE_UE_IDENTITY_CANNOT_BE_DERIVED_BY_THE_NETWORK):
        msg = pycrate_mobile.NAS.EMMTrackingAreaUpdateReject()
        # hardcoded Cause #9: UE identity cannot be derived by the network.
        msg[1].set_val([cause])#8 eps..
        return msg.to_bytes()


    # TAU MSG
    def send_TAUReject(self,epcServer,fd, cause_TAUreject,enb_ue_id):
        #parsing.create_NAS_PDU_downlink(
        #    epcServer, parsing.create_NAS_only_TAUReject(cause_TAUreject), enb_ue_id)
        self.create_NAS_PDU_downlink(
            epcServer, fd,self.create_NAS_only_TAUReject(cause_TAUreject), enb_ue_id)

    def send_TAURequest(self,epcServer,fd, enb_ue_id):
        #parsing.create_NAS_PDU_downlink(
        #    epcServer, parsing.create_NAS_only_TAURequest(), enb_ue_id)
        self.create_NAS_PDU_downlink(
            epcServer,fd, self.create_NAS_only_TAURequest(), enb_ue_id)

    # identity NAS
    def create_NAS_only_identityResponse(self):
        msg = pycrate_mobile.NAS.EMMIdentityResponse()
        msg['ID'].set_IE(val={'type': 1, 'ident': '208100123456789'})
        return msg.to_bytes()
    def create_NAS_only_identityRequest(self):
        return pycrate_mobile.NAS.EMMIdentityRequest().to_bytes()

    # identity message
    def send_identityRequest(self,epcServer,fd, enb_ue_id):
        #parsing.create_NAS_PDU_downlink(
        #    epcServer, parsing.create_NAS_only_identityRequest(), enb_ue_id)
        self.create_NAS_PDU_downlink(
            epcServer,fd, self.create_NAS_only_identityRequest(), enb_ue_id)

    def send_identityResponse(self,epcServer, fd,enb_ue_id):
        #parsing.create_NAS_PDU_uplink(
        #    epcServer, parsing.create_NAS_only_identityResponse(), enb_ue_id)
        self.create_NAS_PDU_uplink(
            epcServer,fd, self.create_NAS_only_identityResponse(), enb_ue_id)

    # attach NAS
    #def create_NAS_only_attachReject(self,val: int):
    def create_NAS_only_attachReject(self,val):
        """creates a NAS message of Attach reject with a fixed cause -> 
        Cause #7 - UE identity cannot be derived by the network."""
        """
        if val > 255 or val < 0:  # just to be sure
            raise Exception("illegal cause code for Attach reject")
        msg = pycrate_mobile.NAS.EMMAttachReject()
        tmp_list = []
        tmp_list.append(val.to_bytes(1, byteorder='big'))
        msg['EMMCause'].set_val(tmp_list)
        """
        msg = pycrate_mobile.NAS.EMMAttachReject()
        msg['EMMCause'].set_val([val])
        return msg.to_bytes()
    # attach message

    def send_attachReject(self,epcServer,fd, enb_ue_id,cause= LIBLTE_MME_EMM_CAUSE_IMPLICITLY_DETACHED):
        """Sends an attach reject message with the given cause.
        Interesting causes for attach reject:
        #3 Illegal UE
        #6 Illegal ME
        #7 EPS services not allowed
        #8 EPS services and non-EPS services not allowed
        #111 Protocol error, unspecified
        """
        #parsing.create_NAS_PDU_downlink(
        #    epcServer, parsing.create_NAS_only_attachReject(epcServer.attach_reject_reason), enb_ue_id)
        #cause = epcServer.attach_reject_reason
        print(f'cause of reject {cause}')
        self.create_NAS_PDU_downlink(
             epcServer,fd, self.create_NAS_only_attachReject(cause), enb_ue_id)
    
    # create S1 encapsulation message

    def create_NAS_PDU_uplink(self,epcServer,fd, nas_param, enb_ue_id):
        IEs = []
        IEs.append({'id': 0, 'criticality': 'reject',
                   'value': ('MME-UE-S1AP-ID', enb_ue_id)})
        IEs.append({'id': 8, 'criticality': 'reject',
                   'value': ('ENB-UE-S1AP-ID', enb_ue_id)})
        IEs.append({'id': 26, 'criticality': 'reject',
                   'value': ('NAS-PDU', nas_param)})
        val = ('initiatingMessage', {'procedureCode': 13, 'criticality': 'ignore', 'value': (
            'DownlinkNASTransport', {'protocolIEs': IEs})})
        #PDU = S1AP.S1AP_PDU_Descriptions.S1AP_PDU
        #PDU.set_val(val)
        #epcServer.send_packet(fd,PDU.to_aper().hex())
        epcServer.encode_and_send_packet(val,fd)

    def create_NAS_PDU_downlink(self,epcServer,fd, nas_param, enb_ue_id: int):
        """Creates a NAS-PDU downlink message for S1AP protocol. 
        Encapsulates a NAS message for communication between MME and UE"""
        IEs = []
        IEs.append({'id': 0, 'criticality': 'reject',
                   'value': ('MME-UE-S1AP-ID', enb_ue_id)})
        IEs.append({'id': 8, 'criticality': 'reject',
                   'value': ('ENB-UE-S1AP-ID', enb_ue_id)})
        IEs.append({'id': 26, 'criticality': 'reject',
                   'value': ('NAS-PDU', nas_param)})
        val = ('initiatingMessage', {'procedureCode': 11, 'criticality': 'ignore', 'value': (
            'DownlinkNASTransport', {'protocolIEs': IEs})})
        #PDU = S1AP.S1AP_PDU_Descriptions.S1AP_PDU
        #PDU.set_val(val)
        #epcServer.send_packet(fd,PDU.to_aper().hex())
        epcServer.encode_and_send_packet(val,fd)

        # parsing.send_attachReject(epcServer,8)
        # parsing.send_identityResponse(epcServer)
        # parsing.send_TAURequest(epcServer)
        # parsing.send_TAUReject(epcServer)
