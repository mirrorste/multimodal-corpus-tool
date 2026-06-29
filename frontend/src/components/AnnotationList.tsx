import React, { useState } from 'react';
import { Table, Tabs, Button, message } from 'antd';
import axios from 'axios';

const { TabPane } = Tabs;

function AnnotationList() {
  const [activeTab, setActiveTab] = useState('metaphors');

  const handleFetchMetaphors = async () => {
    try {
      const response = await axios.get('/api/v1/annotations/metaphors');
      console.log('Metaphors:', response.data);
      message.success('隐喻标注获取成功');
    } catch (error) {
      message.error('获取失败');
    }
  };

  const handleFetchUntranslatability = async () => {
    try {
      const response = await axios.get('/api/v1/annotations/untranslatability');
      console.log('Untranslatability:', response.data);
      message.success('不可译性标注获取成功');
    } catch (error) {
      message.error('获取失败');
    }
  };

  const metaphorColumns = [
    { title: '标注ID', dataIndex: 'id', key: 'id' },
    { title: '隐喻类型', dataIndex: 'type', key: 'type' },
    { title: '源域', dataIndex: 'source_domain', key: 'source_domain' },
    { title: '目标域', dataIndex: 'target_domain', key: 'target_domain' },
    { title: '触发词', dataIndex: 'trigger', key: 'trigger' },
    { title: '置信度', dataIndex: 'confidence', key: 'confidence' },
    { title: '操作', key: 'action', render: () => <Button size="small">编辑</Button> },
  ];

  const untransColumns = [
    { title: '标注ID', dataIndex: 'id', key: 'id' },
    { title: '不可译类型', dataIndex: 'type', key: 'type' },
    { title: '类别', dataIndex: 'category', key: 'category' },
    { title: '描述', dataIndex: 'description', key: 'description' },
    { title: '严重程度', dataIndex: 'severity', key: 'severity' },
    { title: '置信度', dataIndex: 'confidence', key: 'confidence' },
    { title: '操作', key: 'action', render: () => <Button size="small">编辑</Button> },
  ];

  const data = [];

  return (
    <div>
      <h2>标注管理</h2>
      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        <TabPane tab="隐喻标注" key="metaphors">
          <Button type="primary" onClick={handleFetchMetaphors} style={{ marginBottom: 16 }}>
            刷新数据
          </Button>
          <Table dataSource={data} columns={metaphorColumns} rowKey="id" />
        </TabPane>
        <TabPane tab="不可译性标注" key="untranslatability">
          <Button type="primary" onClick={handleFetchUntranslatability} style={{ marginBottom: 16 }}>
            刷新数据
          </Button>
          <Table dataSource={data} columns={untransColumns} rowKey="id" />
        </TabPane>
      </Tabs>
    </div>
  );
}

export default AnnotationList;
