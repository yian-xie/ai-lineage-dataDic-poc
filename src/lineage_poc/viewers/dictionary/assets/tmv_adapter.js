(function(root){
'use strict';
var Original=root.DDCore,active=null;
var names=['asset_registry.csv','field_catalog.csv','data_dictionary.csv'];
var key=function(raw,id){return JSON.stringify([raw.graph_id,raw.snapshot_id,id]);};
var scope=function(raw){return JSON.stringify([raw.graph_id,raw.snapshot_id]);};
function require(ok,message){if(!ok)throw new Error(message);}
function parsedJSON(raw){var result={};Object.keys(raw).forEach(function(name){if(/_json$/.test(name))result[name]=raw[name].trim()?JSON.parse(raw[name]):null;});return result;}
function alias(raw,name,value){if(!Object.prototype.hasOwnProperty.call(raw,name))Object.defineProperty(raw,name,{value:value,enumerable:false});}
function fieldObject(field,relation){return {field_id:field.field_id,field_name:field.field_name,object:relation,description:field.description,data_type:field.data_type,metadata:parsedJSON(field)};}
function operation(raw){var binding={};binding[raw.target_field_id]=[{field_id:raw.source_field_id,role:'value_dependency'}];var expressions={};expressions[raw.target_field_id]=raw.transformation_expression;return {
 relationship_id:'tmv-mapping:'+raw.dictionary_entry_id,operation_type:raw.mapping_kind||'sql_projection',process_name:raw.mapping_kind==='csharp_event_assignment'?'C# entity/event assignment':raw.mapping_kind&&raw.mapping_kind!=='sql_projection'?'EF property/column binding':'Recorded SQL projection',status:'declared',
 source_field_ids:[raw.source_field_id],target_field_ids:[raw.target_field_id],expression:raw.transformation_expression,
 output_input_bindings_json:binding,output_expressions_json:expressions,
 dependency_role:raw.mapping_kind&&raw.mapping_kind!=='sql_projection'?'Repository-declared CLR property binding, not runtime value processing.':'One recorded source-to-target mapping; the SQL expression may have additional mapped operands.',
 confidence_score_10:null,confidence_state:'unscored',confidence_method:'',confidence_rationale:'No numeric relationship assessment supplied.',confidence_assessment_json:null,
 original_assessments_json:[{label:raw.confidence,scope:'recorded TMV mapping'}],
 evidence_json:[{source_path:raw.source_path,input_pointer:raw.original_record_pointer,expression:raw.transformation_expression,verification_mode:'recorded_snapshot'}],
 dictionary_entry_ids:[raw.dictionary_entry_id],review_notes_json:[]
};}
function prepareDataset(parsed){
 require(parsed&&Array.isArray(parsed.rows)&&parsed.rows.length,'TMV dictionary has no rows.');
 ['contract_version','graph_id','snapshot_id','dictionary_entry_id','source_field_id','target_field_id','source_relation','source_column','target_relation','target_column','source_description','target_description','transformation_expression','confidence','source_path'].forEach(function(name){require(parsed.headers.includes(name),'TMV dictionary is missing '+name);});
 var seen=new Set(),sources=new Set(),targets=new Set(),operations=Object.create(null),snapshots=new Set(),allFields=new Set();
 var rows=parsed.rows.map(function(input){
  var raw=Object.assign({},input),json=parsedJSON(raw);
  require(raw.contract_version==='tmv-dictionary-v1','Unsupported TMV contract.');
  require(raw.graph_id&&raw.snapshot_id&&raw.dictionary_entry_id&&raw.source_field_id&&raw.target_field_id,'TMV dictionary identity is missing.');
  require(!seen.has(key(raw,raw.dictionary_entry_id)),'Duplicate TMV dictionary identity.');seen.add(key(raw,raw.dictionary_entry_id));
  var source=active&&active.fieldMap.get(key(raw,raw.source_field_id)),target=active&&active.fieldMap.get(key(raw,raw.target_field_id));
  var sourceNode=fieldObject(source?source.raw:{field_id:raw.source_field_id,field_name:raw.source_column,description:raw.source_description},raw.source_relation);
  var targetNode=fieldObject(target?target.raw:{field_id:raw.target_field_id,field_name:raw.target_column,description:raw.target_description},raw.target_relation);
  var op=operation(raw),catalog={};catalog[raw.source_field_id]=sourceNode;catalog[raw.target_field_id]=targetNode;
  var outputScope={};outputScope[op.relationship_id]=[raw.target_field_id];
  json.operation_output_scope_json=outputScope;json.field_catalog_json=[sourceNode,targetNode];json.process_details_json=[op];json.path_details_json=[];json.review_notes_json=[];
  json.rename_details_json=[{source_field_id:raw.source_field_id,target_field_id:raw.target_field_id,source_column:raw.source_column,target_column:raw.target_column}];
  json.datatype_observations_json=target?[{target_field_id:raw.target_field_id,data_type:target.raw.data_type}]:[];
  var metadata=target&&active.assetMap.get(key(raw,target.raw.asset_id));
  alias(raw,'source_entry_id',raw.source_field_id);alias(raw,'ultracs_field_name',raw.source_column);alias(raw,'source_locator',raw.source_relation+'.'+raw.source_column);
  alias(raw,'source_name_origin',raw.mapping_kind&&raw.mapping_kind!=='sql_projection'?'recorded_clr_property':'recorded_sql_column');alias(raw,'snowflake_table',raw.target_relation);alias(raw,'snowflake_column',raw.target_column);
  alias(raw,'snowflake_description',raw.target_description);alias(raw,'snowflake_stage',metadata&&metadata.json.metadata_json?metadata.json.metadata_json.layer||'':'');
  alias(raw,'snowflake_data_type',target?target.raw.data_type:'');alias(raw,'original_mapping_confidence',raw.confidence);
    alias(raw,'source_data_type',source?source.raw.data_type:'');alias(raw,'source_program',raw.source_path);alias(raw,'ultracs_source_path',raw.source_path);
  alias(raw,'process_summary',raw.transformation_expression);alias(raw,'rename_summary',raw.source_column+' → '+raw.target_column);
  alias(raw,'source_description_origin',source?source.raw.description_source_type:'');alias(raw,'snowflake_description_origin',target?target.raw.description_source_type:'');
  var row={raw:raw,json:json,id:raw.dictionary_entry_id,key:key(raw,raw.dictionary_entry_id),scope:scope(raw),graphId:raw.graph_id,sourceId:raw.source_field_id,snapshotId:raw.snapshot_id,
  ops:[op],catalog:catalog,reviews:[{code:raw.mapping_kind&&raw.mapping_kind!=='sql_projection'?'STATIC_EF_BINDING':'STATIC_SQL_ONLY',reason:'Repository-static mapping declaration, not runtime verification or a complete cross-repository route.'}],reviewCodes:[raw.mapping_kind&&raw.mapping_kind!=='sql_projection'?'STATIC_EF_BINDING':'STATIC_SQL_ONLY'],needsReview:true,
   sourceDescriptionMissing:!raw.source_description.trim(),targetDescriptionMissing:!raw.target_description.trim(),primary:null,pathComplete:null,pathState:'unknown',
   sourceName:raw.source_column,table:raw.target_relation,column:raw.target_column,stage:raw.snowflake_stage,classification:'',mappingLabel:raw.confidence,relevantFieldIds:[raw.source_field_id,raw.target_field_id]};
  row.searchText=parsed.headers.map(function(name){return raw[name];}).join('\n').toLowerCase();
  sources.add(key(raw,raw.source_field_id));targets.add(key(raw,raw.target_field_id));snapshots.add(raw.snapshot_id);allFields.add(raw.source_field_id);allFields.add(raw.target_field_id);operations[op.relationship_id]=op;
  return row;
 });
 return {headers:parsed.headers.slice(),rows:rows,operationCount:rows.length,sourceCount:sources.size,targetCount:targets.size,fieldCount:allFields.size,snapshots:Array.from(snapshots),operationRegistry:operations};
}
function registry(csv,id){var parsed=Original.parseCSV(csv),seen=new Set();var rows=parsed.rows.map(function(raw){require(raw.contract_version==='tmv-dictionary-v1'&&raw.graph_id&&raw.snapshot_id&&raw[id],'Invalid TMV registry identity.');var identity=key(raw,raw[id]);require(!seen.has(identity),'Duplicate TMV registry identity.');seen.add(identity);return {raw:raw,json:parsedJSON(raw),id:raw[id],key:identity,scope:scope(raw)};});return {headers:parsed.headers,rows:rows};}
function prepareBundle(files,manifest){
 names.forEach(function(name){require(typeof files[name]==='string','TMV bundle is missing '+name);});
 var assets=registry(files[names[0]],'asset_id'),fields=registry(files[names[1]],'field_id');
 var assetMap=new Map(assets.rows.map(function(row){return [row.key,row];})),fieldMap=new Map(fields.rows.map(function(row){return [row.key,row];}));
 var scopes=new Set(assets.rows.map(function(row){return row.scope;})),counts=new Map(),fieldUp=new Map(),fieldDown=new Map(),assetUp=new Map(),assetDown=new Map();
 assets.rows.forEach(function(row){assetUp.set(row.key,new Set());assetDown.set(row.key,new Set());});
 fields.rows.forEach(function(row){require(assetMap.has(key(row.raw,row.raw.asset_id)),'TMV field has missing or cross-snapshot asset.');require(scopes.has(row.scope),'TMV registry snapshot mismatch.');counts.set(key(row.raw,row.raw.asset_id),(counts.get(key(row.raw,row.raw.asset_id))||0)+1);fieldUp.set(row.key,new Set());fieldDown.set(row.key,new Set());row.json.transformation_logic_json=[];});
 var candidate={files:files,manifest:manifest||{},assets:assets,fields:fields,assetMap:assetMap,fieldMap:fieldMap,scopes:Array.from(scopes),key:key};
 var previous=active;active=candidate;var dataset;
 try{
  dataset=prepareDataset(Original.parseCSV(files[names[2]]));
  dataset.rows.forEach(function(row){
   var source=fieldMap.get(key(row.raw,row.raw.source_field_id)),target=fieldMap.get(key(row.raw,row.raw.target_field_id));
   require(source&&target,'TMV mapping has missing or cross-snapshot field endpoints.');
   require(row.raw.source_description===source.raw.description&&row.raw.target_description===target.raw.description,'TMV description mirrors disagree.');
   require(row.raw.source_column===source.raw.field_name&&row.raw.target_column===target.raw.field_name,'TMV mapping column names disagree with field catalog.');
   require(source.raw.repository===row.raw.repository&&target.raw.repository===row.raw.repository,'TMV mapping repository mismatch.');
   fieldDown.get(source.key).add(target.id);fieldUp.get(target.key).add(source.id);
   var sourceAsset=key(source.raw,source.raw.asset_id),targetAsset=key(target.raw,target.raw.asset_id);
   if(sourceAsset!==targetAsset){assetDown.get(sourceAsset).add(target.raw.asset_id);assetUp.get(targetAsset).add(source.raw.asset_id);}
   source.json.transformation_logic_json.push(Object.assign({field_role:'input'},row.ops[0]));target.json.transformation_logic_json.push(Object.assign({field_role:'output'},row.ops[0]));
  });
 }catch(error){active=previous;throw error;}
 fields.rows.forEach(function(row){
  var raw=row.raw,asset=assetMap.get(key(raw,raw.asset_id)),provenance=row.json.description_provenance_json||{};
  alias(raw,'source_system',raw.repository);alias(raw,'layer',(asset.json.metadata_json||{}).layer||'');alias(raw,'field_kind',raw.repository==='kb-accounts'?((asset.json.metadata_json||{}).kind==='CLR_ENTITY'?'clr_property':(asset.json.metadata_json||{}).kind==='CLR_EVENT_CONTRACT'?'clr_event_property':'repository_declared_database_column'):'sql_referenced_relation_column');
  alias(raw,'description_origin',raw.description_source_type);alias(raw,'description_generator',provenance.generator||'');alias(raw,'description_author','');
  alias(raw,'source_locator',raw.relation_id+'.'+raw.field_name);alias(raw,'physical_binding_status','repository_declared_not_runtime_verified');
  alias(raw,'source_file','');row.json.upstream_field_ids_json=Array.from(fieldUp.get(row.key));row.json.downstream_field_ids_json=Array.from(fieldDown.get(row.key));
  row.json.original_field_json=Object.assign({},raw);
 });
 assets.rows.forEach(function(row){var raw=row.raw,metadata=row.json.metadata_json||{};alias(raw,'source_system',raw.repository);alias(raw,'layer',metadata.layer||'');alias(raw,'asset_kind',metadata.kind||'declared_relation');alias(raw,'field_count',String(counts.get(row.key)||0));alias(raw,'physical_binding_status','repository_declared_not_runtime_verified');alias(raw,'physical_asset_name',raw.asset_name);row.json.upstream_asset_ids_json=Array.from(assetUp.get(row.key));row.json.downstream_asset_ids_json=Array.from(assetDown.get(row.key));});
 candidate.dictionary={headers:dataset.headers,rows:dataset.rows};candidate.operationCount=dataset.operationCount;
 active=candidate;
 return candidate;
}
function tmv(parsed){return parsed&&parsed.headers&&parsed.headers.includes('contract_version')&&parsed.rows&&parsed.rows.length&&parsed.rows.every(function(row){return row.contract_version==='tmv-dictionary-v1';});}
root.DDCore=Object.freeze(Object.assign({},Original,{prepareDataset:function(parsed){return tmv(parsed)?prepareDataset(parsed):Original.prepareDataset(parsed);}}));
root.TMVViewerAdapter=Object.freeze({prepareDataset:prepareDataset,prepareBundle:prepareBundle,installBundle:function(){var original=root.V3Bundle;root.V3Bundle=Object.freeze(Object.assign({},original,{prepareBundle:function(files,manifest){var parsed=Original.parseCSV(files['data_dictionary.csv']||'');return tmv(parsed)?prepareBundle(files,manifest):original.prepareBundle(files,manifest);}}));}});
})(window);