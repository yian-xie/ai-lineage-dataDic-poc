# Schema Node Groups

## Group 1: Source
Generic label: "Source"
Expands to: MV_FILE

## Group 2: Extract
Generic label: "Extract"
Expands to: Extract_PROGRAM, Extract_FILE

## Group 3: Staging Movement
Generic label: "Staging Movement"
Expands to: HVR_CHANNEL, HVR_LOCATION

## Group 4: Transform Jobs
Generic label: "Transform Jobs"
Expands to: AIRFLOW_DAG, AIRFLOW_TASK, 
            DBT_MODEL, SCHEMACHANGE_MIGRATION, CDP_PRODUCT

## Group 5: Destination
Generic label: "Destination"
Expands to: S3_PATH, SNOWFLAKE_RELATION