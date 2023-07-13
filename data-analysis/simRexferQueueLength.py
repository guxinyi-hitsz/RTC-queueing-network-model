# %%
"""
Author:        guxinyi@agora.io
Last Modified: 17-Nov-2021
"""
import pandas as pd
import re
import simpy

media_log = "eth0_audience_video4.csv"
rexfer_log = "eth0_video4_arq_res.csv"
request_log = "eth0_video_rex_req_v3.csv"

media_df = pd.read_csv(media_log, index_col=False)
rexfer_df = pd.read_csv(rexfer_log, index_col=False)
request_df = pd.read_csv(request_log, index_col=False)

#media_df[media_df[["seq"]].duplicated()].count()
#media_df[["frame_type"]].value_counts()

total_request_times = request_df["count"].sum()
total_rexfer_times = rexfer_df.shape[0]
print(f"总请求次数: {total_request_times}")
print(f"总重传次数: {total_rexfer_times}")
print(f"重传率: {total_rexfer_times/total_request_times:.3%}")

# This function aims to parse "losts" string, and return a list of seqs.
def parseLosts(this_str, size):
    results = []
    pattern = re.compile(r"\d+")
    matched = pattern.findall(this_str)
    #assert (len(matched), size)
    base_seq = 0
    for i, m in enumerate(matched):
        if i == 0:
            base_seq = int(m)
        else:
            results.append(int(m) + base_seq)
    return results


# This function aims to parse "losts" string, separate a single entry to multiple entrys, and get a new dataframe.
def transform_request_df(this_df):
    new_dicts = []
    for request_msg in this_df.itertuples(name="request_msg"):
        #assert (request_msg.Protocol, "UDP1.VIDEO_REX_REQ_V3")

        truncated = 60
        results = []
        if request_msg.count > truncated:
            results += parseLosts(request_msg.losts, truncated)
            results += parseLosts(
                request_msg.losts_extend, request_msg.count - truncated
            )
        else:
            results += parseLosts(request_msg.losts, request_msg.count)

        for i in range(int(request_msg.count)):
            this_dict = {}
            this_dict["Time"] = request_msg.Time
            this_dict["Protocol"] = request_msg.Protocol
            this_dict["seq"] = results[i]
            new_dicts.append(this_dict)

    new_df = pd.DataFrame(new_dicts)
    return new_df


def transform_rexfer_df(this_df):
    new_df = this_df[["Time", "Protocol", "seq"]]
    return new_df

df_rex = transform_rexfer_df(rexfer_df)
df_req = transform_request_df(request_df)

df_combined = pd.concat([df_req, df_rex], ignore_index=True)
df_combined.sort_values(
    by=["Time", "seq"], axis=0, ascending=[True, True], inplace=True
)
df_combined.reset_index(drop=True, inplace=True)
df_combined.to_csv("req_and_rex.csv")

class PacerQueue:
    def __init__(self, this_df):
        self.env = simpy.Environment()
        self.length = 0
        self.df = this_df
        self.trace = []

    def change_queue(self, timestamp, protocol):
        yield self.env.timeout(timestamp)
        if protocol == "UDP1.VIDEO_REX_REQ_V3":
            self.length += 1
            self.trace.append({'Time':timestamp,'Length':self.length})
        elif protocol == "UDP1.VIDEO4_ARQ_RES":
            self.length -= 1
            self.trace.append({'Time':timestamp,'Length':self.length})
        
    def run(self):
        for log in self.df.itertuples(name="log"):
            self.env.process(self.change_queue(log.Time,log.Protocol))
        self.env.run()
        new_trace = pd.DataFrame(self.trace)
        return new_trace
    
simQueue = PacerQueue(df_combined)
df_trace = simQueue.run()
df_trace.to_csv("queue_length.csv")