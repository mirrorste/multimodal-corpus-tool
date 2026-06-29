import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, Select, message } from 'antd';
import axios from 'axios';
import { PlusOutlined, PlayCircleOutlined, DeleteOutlined } from '@ant-design/icons';

interface Video {
  id: string;
  url: string;
  platform: string;
  title: string | null;
  status: string;
  created_at: string;
}

const { Option } = Select;

function TaskList() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchVideos();
  }, []);

  const fetchVideos = async () => {
    try {
      const response = await axios.get('/api/v1/videos');
      setVideos(response.data);
    } catch (error) {
      message.error('获取视频列表失败');
    }
  };

  const handleAddVideo = async () => {
    try {
      const values = await form.validateFields();
      await axios.post('/api/v1/videos', values);
      message.success('视频添加成功');
      setIsModalVisible(false);
      form.resetFields();
      fetchVideos();
    } catch (error) {
      message.error('添加失败');
    }
  };

  const handleDeleteVideo = async (id: string) => {
    try {
      await axios.delete(`/api/v1/videos/${id}`);
      message.success('删除成功');
      fetchVideos();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleProcessVideo = async (id: string) => {
    try {
      await axios.post(`/api/v1/tasks/${id}/process`);
      message.success('任务开始处理');
      fetchVideos();
    } catch (error) {
      message.error('处理失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
    { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
    { title: '链接', dataIndex: 'url', key: 'url', ellipsis: true },
    { title: '平台', dataIndex: 'platform', key: 'platform' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const statusMap: Record<string, string> = {
          pending: '待处理',
          downloading: '下载中',
          processing: '处理中',
          done: '完成',
          failed: '失败',
          cancelled: '已取消',
        };
        return statusMap[status] || status;
      },
    },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at' },
    {
      title: '操作',
      key: 'action',
      render: (_, record: Video) => (
        <>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            size="small"
            onClick={() => handleProcessVideo(record.id)}
            disabled={record.status === 'processing' || record.status === 'done'}
          >
            处理
          </Button>
          <Button
            danger
            icon={<DeleteOutlined />}
            size="small"
            onClick={() => handleDeleteVideo(record.id)}
            style={{ marginLeft: 8 }}
          >
            删除
          </Button>
        </>
      ),
    },
  ];

  return (
    <div>
      <Button
        type="primary"
        icon={<PlusOutlined />}
        onClick={() => setIsModalVisible(true)}
        style={{ marginBottom: 16 }}
      >
        添加视频
      </Button>
      <Table
        dataSource={videos}
        columns={columns}
        rowKey="id"
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title="添加视频"
        visible={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        onOk={handleAddVideo}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="url"
            label="视频链接"
            rules={[{ required: true, message: '请输入视频链接' }]}
          >
            <Input placeholder="https://www.youtube.com/watch?v=xxx" />
          </Form.Item>
          <Form.Item
            name="platform"
            label="平台"
            rules={[{ required: true, message: '请选择平台' }]}
          >
            <Select placeholder="请选择平台">
              <Option value="youtube">YouTube</Option>
              <Option value="bilibili">Bilibili</Option>
              <Option value="vimeo">Vimeo</Option>
              <Option value="local">本地</Option>
            </Select>
          </Form.Item>
          <Form.Item name="preferred_resolution" label="分辨率">
            <Select defaultValue="1080p">
              <Option value="720p">720p</Option>
              <Option value="1080p">1080p</Option>
              <Option value="4k">4K</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default TaskList;
