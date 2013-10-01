from PySide.QtCore import *
from PySide.QtGui import *
from database import *

class DataTree(QTreeView):

    def __init__(self,parent=None,mainWindow=None):
        super(DataTree,self).__init__(parent)
        self.mainWindow=mainWindow
                
        #self.setSortingEnabled(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setUniformRowHeights(True)
                

    def loadData(self,database):
        self.treemodel = TreeModel(self.mainWindow,database)
        self.setModel(self.treemodel)
        
        #self.proxymodel =  QSortFilterProxyModel(self)
        #self.proxymodel.setSourceModel(self.treemodel)        
        #self.setModel(self.proxymodel)

    @Slot()
    def currentChanged(self,current,previous):
        self.mainWindow.detailTree.clear()
        if current.isValid():     
            item=current.internalPointer()
            self.mainWindow.detailTree.showDict(item.data['response'])
        
        #select level
        level=0
        c=current
        while c.isValid():
            level += 1
            c=c.parent()
        
        self.mainWindow.levelEdit.setValue(level)
            
            
    def selectedIndexesAndChildren(self,level=None,persistent=False,emptyonly=False):
        selected=[x for x in self.selectedIndexes() if x.column()==0]
        filtered=[]

        def getLevel(index):
            if not index.isValid():
                return 0
            
            treeitem=index.internalPointer()
            if (treeitem.data != None) and (treeitem.data['level'] != None):
                return treeitem.data['level']+1
            else:
                return 0

            
        def addIndex(index):
            if index not in filtered:
                #child=index.child(0,0)
                
                if level==None or level==getLevel(index):
                    
                    if emptyonly:
                        child=index.child(0,0)
                        append = not child.isValid()
                    else:
                        append=True    
                    
                    if append==True:
                        if persistent:
                            filtered.append(QPersistentModelIndex(index))
                        else:
                            filtered.append(index)    
                
                if level==None or level>getLevel(index) :
                    self.model().fetchMore(index)
                    child=index.child(0,0)
                    while child.isValid():
                        addIndex(child)
                        child=index.child(child.row()+1,0)
                            
        
        for index in selected:
            addIndex(index)
            
        return filtered     

      
                           
class TreeItem(object):
    def __init__(self, parent=None,id=None,data=None):
        self.id = id
        self.parentItem = parent        
        self.data = data
        self.childItems = []
        self.loaded=False                
        self._childcountallloaded=False
        self._childcountall=0

    def appendChild(self, item,persistent=False):
        item.parentItem=self
        self.childItems.append(item)
        if persistent:
            self._childcountall += 1

    def child(self, row):
        return self.childItems[row]
    
    def clear(self):
        self.childItems=[]
        self.loaded=False
        self._childcountallloaded=False
        
    def remove(self,persistent=False):
        self.parentItem.removeChild(self,persistent)            
        

    def removeChild(self,child,persistent=False):
        if child in self.childItems:            
            self.childItems.remove(child)
            if persistent:
                self._childcountall -= 1        
        
    def childCount(self):
        return len(self.childItems)
    
    def childCountAll(self):       
        if not self._childcountallloaded:                                     
            self._childcountall=Node.query.filter(Node.parent_id == self.id).count()
            self._childcountallloaded=True            
        return self._childcountall     
            
    def parent(self):
        return self.parentItem
    
    def parentid(self):
        return self.parentItem.id if self.parentItem else None     

    def level(self):
        if self.data == None:
            return 0
        else:
            return self.data['level']

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)
        return 0

    

class TreeModel(QAbstractItemModel):
    
    def __init__(self, mainWindow=None,database=None):
        super(TreeModel, self).__init__()
        self.mainWindow=mainWindow
        self.customcolumns=[]
        self.rootItem = TreeItem()
        self.database=database
        #self.requester=ApiRequester(mainWindow)

    def reset(self):        
        self.rootItem.clear()
        super(TreeModel, self).reset()        
                   
    def setCustomColumns(self,newcolumns=[]):
        self.customcolumns=newcolumns
        self.layoutChanged.emit()    
                            
    def delete(self,level,querytype):
        if (not self.database.connected):
            return False                                               

        #self.beginRemoveRows(index.parent(),index.row(),index.row())
        #item=index.internalPointer()                 
        self.beginResetModel()  
        Node.query.filter(Node.level == level,Node.querytype==querytype).delete()                            
        self.database.session.commit()                         
        #item.remove(True)
        
        self.reset()
        self.endResetModel()
        #self.reset()       
        #self.endRemoveRows()


    def deleteNode(self,index):
        if (not self.database.connected) or (not index.isValid()) or (index.column() <> 0):
            return False                                               

        self.beginRemoveRows(index.parent(),index.row(),index.row())
        item=index.internalPointer()
        
        
        #Node.query.filter(Node.id == item.parentid).update()
                           
        Node.query.filter(Node.id == item.id).delete()                            
        self.database.session.commit()                         
        item.remove(True)       
        self.endRemoveRows()

            
    def addNodes(self,objectids):
        try:       
            if not self.database.connected:
                return False
                
            #self.beginInsertRows(QModelIndex(),self.rootItem.childCount(),self.rootItem.childCount()+len(facebookids)-1)
            newnodes=[]   
            for objectid in objectids: 
                new=Node(objectid)
                newnodes.append(new)
                
                #self.database.session.flush()
                #itemdata=self.getItemData(new)     
                #self.rootItem.appendChild(TreeItem(self.rootItem,new.id,itemdata),True)

            self.database.session.add_all(newnodes)             
            self.database.session.commit()
            self.rootItem._childcountall+=len(objectids)
            self.layoutChanged.emit()
                                    
            #self.endInsertRows()
        except Exception as e:
            QMessageBox.critical(self.mainWindow,"Facepager",str(e))                    

            
    def queryData(self,index,module,options):
        try:
            if not index.isValid(): return False
                
            treenode=index.internalPointer()
            dbnode=Node.query.get(treenode.id)
            if not dbnode: return False

            for page in range(0,options.get('pages',1)): 
                
                #get data
                try:                
                    querytime = datetime.datetime.now()
                    response,paging = module.fetchData(treenode.data,options)
      
                except Exception as e:
                    querystatus=str(type(e))+str(e)
                    self.mainWindow.logmessage(querystatus)
                    
                    response={}
                    paging = False
                else:
                    querystatus="fetched"                
                
                
                #append nodes
                if options.get('append',True):
        
                    #filter response
                    if options['nodedata'] != None:
                        nodes=getDictValue(response,options['nodedata'],False)                    
                    else:
                        nodes=response                                
                    
                    #single record
                    if not (type(nodes) is list): nodes=[nodes]                                     
                    
                    #empty records                    
                    if (len(nodes) == 0) and (options.get('appendempty',True)):                    
                        nodes=[{}]
                        querystatus="empty"                      
                    
                    #extracted nodes                    
                    newnodes=[]
                    for n in nodes:                    
                        new=Node(getDictValue(n,options.get('objectid',"")),dbnode.id)
                        new.objecttype='data'
                        new.response=n
                        new.level=dbnode.level+1
                        new.querystatus=querystatus
                        new.querytime=str(querytime)
                        new.querytype=options['querytype']
                        new.queryparams=options                                        
                        newnodes.append(new)
                    
                    #Offcut
                    if (options['nodedata'] != None) and (options.get('appendoffcut',True)):
                        offcut = filterDictValue(response,options['nodedata'],False)
                        new=Node(dbnode.objectid,dbnode.id)
                        new.objecttype='offcut'
                        new.response=offcut
                        new.level=dbnode.level+1
                        new.querystatus=querystatus
                        new.querytime=str(querytime)
                        new.querytype=options['querytype']
                        new.queryparams=options
                        
                        newnodes.append(new)                                            
        
                    self.database.session.add_all(newnodes)    
                    treenode._childcountall += len(newnodes)    
                    dbnode.childcount += len(newnodes)    
                    self.database.session.commit()                
                    
                #update node    
                else:  
                    dbnode.response = response
                    dbnode.querystatus=querystatus                
                    dbnode.querytime=str(datetime.datetime.now())
                    dbnode.querytype=options['querytype']
                    dbnode.queryparams=json.dumps(options)
                    self.database.session.commit()
                    treenode.data=self.getItemData(dbnode)
    
                self.layoutChanged.emit()
                
                options = paging
                if paging == False: break
                
        except Exception as e:
            self.mainWindow.logmessage(str(e))

    def unpackList(self,index,key):
        try:
            if not index.isValid():
                return False
                
            treenode=index.internalPointer()
            dbnode=Node.query.get(treenode.id)
                
            nodes=getDictValue(dbnode.response,key,False)
            if not (type(nodes) is list): return False                                     
            
            #extract nodes                    
            newnodes=[]
            for n in nodes:                    
                new=Node(dbnode.objectid,dbnode.id)
                new.objecttype='unpacked'
                new.response=n
                new.level=dbnode.level+1
                new.querystatus=dbnode.querystatus
                new.querytime=dbnode.querytime
                new.querytype=dbnode.querytype
                new.queryparams=dbnode.queryparams                                        
                newnodes.append(new)
            

            self.database.session.add_all(newnodes)    
            treenode._childcountall += len(newnodes)    
            dbnode.childcount += len(newnodes)    
            self.database.session.commit()                
            self.layoutChanged.emit()
                
        except Exception as e:
            self.mainWindow.logmessage(str(e))                            
                                
    def columnCount(self, parent):
        return 5+len(self.customcolumns)    

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()
                                             

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            captions=['Object ID','Object Type','Query Status','Query Time','Query Type']+self.customcolumns                
            return captions[section] if section < len(captions) else ""

        return None

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()
        
          
    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

            
    def data(self, index, role):
        if not index.isValid():
            return None

        if role != Qt.DisplayRole:
            return None

        item = index.internalPointer()
        
        if index.column()==0:
            return item.data['objectid']
        elif index.column()==1:
            return item.data['objecttype']              
        elif index.column()==2:
            return item.data['querystatus']      
        elif index.column()==3:
            return item.data['querytime']      
        elif index.column()==4:
            return item.data['querytype']      
        else:            
            return getDictValue(item.data['response'],self.customcolumns[index.column()-5])
            

    def hasChildren(self, index):
        if not self.database.connected:
            return False
                
        if not index.isValid():
            item = self.rootItem
        else:
            item = index.internalPointer()                                
        
        return item.childCountAll() > 0               
            
        
            

    def getItemData(self,item):
        itemdata={}
        itemdata['level']=item.level
        itemdata['objectid']=item.objectid
        itemdata['objecttype']=item.objecttype        
        itemdata['querystatus']=item.querystatus
        itemdata['querytime']=item.querytime
        itemdata['querytype']=item.querytype
        itemdata['queryparams']=item.queryparams
        itemdata['response']=item.response     
        return itemdata   
        
    def canFetchMore(self, index):                           
        if not self.database.connected:
            return False
        
        if not index.isValid():
            item = self.rootItem
        else:
            item = index.internalPointer()    
                            
        return item.childCountAll() > item.childCount()
        
    def fetchMore(self, index):
        if not index.isValid():
            parent = self.rootItem
        else:
            parent = index.internalPointer()                       
        
        if parent.childCountAll() == parent.childCount():
            return False
                
        row=parent.childCount()        
        items = Node.query.filter(Node.parent_id == parent.id).offset(row).all()

        
        self.beginInsertRows(index,row,row+len(items)-1)

        for item in items:
            itemdata=self.getItemData(item)
            new=TreeItem(parent,item.id,itemdata)
            new._childcountall=item.childcount
            new._childcountallloaded=True                                                               
            parent.appendChild(new)
            self.createIndex(row, 0, index)
            row += 1
                                        
        self.endInsertRows()
        parent.loaded=parent.childCountAll()==parent.childCount()