import React from 'react';
import { Table, Button, message } from 'antd';
import axios from 'axios';
import { DownloadOutlined } from '@ant-design/icons';

function CorpusList() {
  const handleExport = async (videoId: string) => {
    try {
      await axios.get(`/api/v1/corpus/${videoId}/export`);
      message.success('导出成功');
    } catch (error) {
      message.error('导出失败');
    }
  };

  const columns = [
    { title: '视频ID', dataIndex: 'video_id', key: 'video_id' },
    { title: '标题', dataIndex: 'title', key: 'title' },
    { title: '处理状态', dataIndex: 'status', key: 'status' },
    { title: '语料数量', dataIndex: 'corpus_count', key: 'corpus_count' },
    {
      title: '操作',
      key: 'action',
      render: (_, record: any) => (
        <Button
          type="primary"
          icon={<DownloadOutlined />}
          size="small"
          onClick={() => handleExport(record.video_id)}
        >
          导出
        </Button>
      ),
    },
  ];

  const data = [];

  return (
    <div>
      <h2>语料库</h2>
      <Table dataSource={data} columns={columns} rowKey="video_id" />
    </div>
  );
}

export default CorpusList;
