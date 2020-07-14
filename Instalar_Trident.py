import requests
import time
import json
import texttable as tt
import settings_config as cfg
import yaml
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def login(req,base_url,username,password):
    
    print("Obteniendo token...")
    
    header = {"content-type": "application/json"}
    
    #Obtenemos domain, audience y clientId necesarios para payload de autenticación
    r = req.get(url="https://occm.demo.netapp.com:443/occm/api/occm/system/support-services", headers=header, verify=False)
    
    respuesta = r.json()
    print("domain: ", respuesta["portalService"]["auth0Information"]["domain"])
    domain = respuesta["portalService"]["auth0Information"]["domain"]
    print("audience: ", respuesta["portalService"]["auth0Information"]["audience"])
    audience = respuesta["portalService"]["auth0Information"]["audience"]
    print("clientId: ", respuesta["portalService"]["auth0Information"]["clientId"])
    clientId = respuesta["portalService"]["auth0Information"]["clientId"]

    auth_url = "https://"+domain+"/oauth/token"
    
    auth_payload = {"grant_type":"password","username":username,"password":password,"audience":audience,"scope":"profile","client_id":clientId}
    
    #Hacemos POST para obtener token
    a = req.post(url=auth_url, json=auth_payload, headers=header, verify=False)

    respuesta = a.json()
    token = respuesta["access_token"]
    
    return token

def get_k8s_clusters(req,token):

    #Añadimos el token al header y hacemos get para extraer los clusters k8s ya registrados en OCCM
    hed = {'Authorization': 'Bearer ' + token}
    s = req.get(url="https://occm.demo.netapp.com/occm/api/k8s/clusters", headers=hed, verify=False)
    
    #Formateamos la salida haciendo uso de la librería texttable
    ctr = 0
    clusters = s.json()
    tab = tt.Texttable()
    header = ['K8s cluster name','clusterEndpoint','k8sVersion','tridentVersion']
    tab.header(header)
    tab.set_cols_align(['c','c','c','c'])
    for i in clusters:
        ctr = ctr + 1
        clus = i['clusterName']
        cep = i['clusterEndpoint']
        ver = i['k8sVersion']
        trid = i['tridentVersion']
        row = [clus,cep,ver,trid]
        tab.add_row(row)
        tab.set_cols_align(['c','c','c','c'])
    print("clusters de K8s en instancia OCCM:{}".format(ctr))
    setdisplay = tab.draw()
    print(setdisplay)


def post_k8s_cluster(req,kubeconfig,contextname,token):

    print("Registramos el K8s cluster => ", contextname)
    
    payload = {"k8sconfig": kubeconfig,"contextNames": [contextname]}
    header_save = {"content-type": "application/json",'Authorization': 'Bearer ' + token}
    b = req.post(url="https://occm.demo.netapp.com/occm/api/k8s/save", json=payload, headers=header_save, verify=False)
    print(b.text) 
    
def install_trident(req,k8sCluster,ontapcluster,ips,token):

    #Obtenemos kubernetes cluster id y workingenvironment id de los clusters pasados en los argumentos
    header_get = {"content-type": "application/json",'Authorization': 'Bearer ' + token}
    r = req.get(url="https://occm.demo.netapp.com/occm/api/k8s/clusters", headers=header_get, verify=False)

    respuesta = r.json()

    k8sClusterId = "0"
    for i in respuesta:
        if i["clusterName"] == k8sCluster:
            k8sClusterId = i["publicId"]
    print(k8sClusterId)
    if k8sClusterId != "0":
        
        r = req.get(url="https://occm.demo.netapp.com/occm/api/working-environments", headers=header_get, verify=False)

        respuesta2 = r.json()
        
        workingEnvironmentId = "0"
        for i in respuesta2["onPremWorkingEnvironments"]:
            if i["name"] == ontapcluster:
                workingEnvironmentId = i["publicId"]
        
        if workingEnvironmentId != "0":
            header = {"content-type": "application/json",'Authorization': 'Bearer ' + token}
            payload = {"ips": [ips],"setDefaultStorageClass": "true","setSanDefaultStorageClass": "false"}
            url_trident = cfg.base_url + "/k8s/connect-on-prem/" + k8sClusterId + "/" + workingEnvironmentId
            print(url_trident)
            b = req.post(url=url_trident, json=payload, headers=header, verify=False)
            print("Instalando Trident en k8s cluster ",k8sCluster,"...")
            time.sleep(5)
                    
        else:
            print("No existe workingenvironment =>",ontapcluster)
    else:
        print("No existe k8s clustert => ", k8sCluster)
            
 
  
    
def main():
    #Abrimos sesión
    s = requests.Session()
    #Llamamos función login para autenticarnos y obtener token
    token = login(s,cfg.base_url,cfg.username,cfg.password)
    
    #Abrimos kubeconfig file local y lo almacenamos como yaml dump
    with open(cfg.kube_config_local) as file:
      kcl = yaml.load(file, Loader=yaml.FullLoader)
    kubeconfig_local = yaml.dump(kcl)

    #Registramos cluster remote de K8s en OCCM     
    post_k8s_cluster(s,kubeconfig_local,cfg.k8s_local_context_name,token)

    #Abrimos kubeconfig file remote y lo almacenamos como yaml dump
    with open(cfg.kube_config_remote) as file:
      kcr = yaml.load(file, Loader=yaml.FullLoader)
    kubeconfig_remote = yaml.dump(kcr)

    #Registramos cluster remote de K8s en OCCM     
    post_k8s_cluster(s,kubeconfig_remote,cfg.k8s_remote_context_name,token)
  
    #Instalamos Trident en el cluster local de K8s
    install_trident(s,"k8s1-onPrem","onPrem","192.168.0.0/24",token)
    
    #Instalamos Trident en el cluster remote de K8s
    install_trident(s,"k8s2-remote","remote","192.168.0.0/24",token)

    print("Verificando registro en OCCM...")
    time.sleep(10)
    #Listamos los clusters de kubernetes vinculados a OCCM
    get_k8s_clusters(s,token)
        
    
    
### Main program    
main()
