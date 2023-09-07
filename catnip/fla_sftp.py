from pydantic import BaseModel, SecretStr
from typing import Optional, List

from paramiko import Transport, SFTPClient, SFTPError
from os import getcwd

import pandas as pd
from pandera import DataFrameModel
from pandera.typing import DataFrame

from datetime import datetime

class FLA_Sftp(BaseModel):

    host: str
    username: str
    password: SecretStr
    remote_path: str

    port: int = 22

    ## Import Pandera Schema
    input_schema: DataFrameModel = None
    output_schema: DataFrameModel = None

    ######################
    ### USER FUNCTIONS ###
    ######################

    def get_all_filenames_in_directory(self) -> List:

        ## Create connection
        conn = self._create_connection()

        ## Get filenames
        filenames = conn.listdir(self.remote_path)
        
        ## Close connection
        conn.close()

        return filenames


    def file_exists(self, conn: SFTPClient) -> bool:

        ## Check file existence
        try:
            conn.stat(self.remote_path)
            return True

        ## Else return error message
        except SFTPError as e:
            print(f"The specified file on this '{self.remote_path}' remote_path does not exist.")
            return False


    def download_csv(self, separator: str = ",") -> pd.DataFrame:

        ## Create connection
        conn = self._create_connection()

        ## Initialize dataframe
        df = pd.DataFrame()

        ## Download csv as dataframe
        if self.file_exists(conn):
            with conn.open(self.remote_path) as file:
                file.prefetch()

                if self.input_schema:
                    df = DataFrame[self.input_schema](pd.read_csv(file, sep = separator))
                else:
                    df = pd.read_csv(file, sep = separator)

        ## Close connection
        conn.close()

        return df


    def download_file(self, temp_filename: str) -> str:

        ## Create connection
        conn = self._create_connection()

        ## Create local path string
        local_path = f"{getcwd()}/{temp_filename}.{self.remote_path.split('.')[1]}"

        ## Download file and write to local path
        conn.get(self.remote_path, local_path)

        ## Close connection
        conn.close()

        ## Notify path
        print(f"Moved {self.remote_path} to {local_path}")

        ## Return written path string
        return local_path
    

    def upload_csv(self, df: pd.DataFrame) -> None:

        ## Update dataframe
        df['processed_date'] = datetime.utcnow()
        if self.output_schema:
            df = self.output_schema.validate(df)
            df = df.reindex(columns = [*self.output_schema.to_schema().columns])

        ## Create connection
        conn = self._create_connection()

        ## Upload csv
        with conn.open(self.remote_path, "w") as file:
            file.write(df.to_csv(index = False))

        ## Close connection
        conn.close()

        return None
    

    ########################
    ### HELPER FUNCTIONS ###
    ########################

    def _create_connection(self) -> Optional[SFTPClient]:

        ## Establish transport object
        transport = Transport((self.host, self.port))
        transport.connect(username = self.username, password = self.password.get_secret_value())

        ## Create SFTP connection object
        connection = SFTPClient.from_transport(transport)        

        return connection