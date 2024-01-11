// ConsoleApplication2.cpp : 此文件包含 "main" 函数。程序执行将在此处开始并结束。
//
#include <windows.h>
#include <iostream>
#include <mutex>
#include <queue>
#include <fstream>

#include <BluetoothAPIs.h>
#include "WCHBLEDLL.h"

#pragma comment(lib,"Bthprops.lib")  
#pragma comment (lib,"WCHBLEDLL.lib")

struct ParamInf
{
	WCHBLEHANDLE DevHandle;
	USHORT ServiceUUID;
	USHORT CharacteristicUUID;
};
HANDLE g_recvevent = NULL;
bool Support = FALSE;
std::mutex g_blerecvcmutex;
char g_blerecvdata[102400] = "";
char g_recvcopybuf[102400] = "";
int g_blerecvlen = 0;
char g_send_char[1030] = "";
int g_send_len = 0;
char g_transbuf[102400] = "";
BLENameDevID g_BLEDev[MAX_PATH];
WCHBLEHANDLE g_devhandle;
char g_blepath[100] = "";
char g_blename[100] = "";
USHORT g_serviceUUID[100] = { 0 };
USHORT g_characteristicUUID[100] = { 0 };
int g_MTU = 0;
ParamInf g_paramInf[MAX_PATH];
std::queue<float> IMU[3];
const int MAXLEN = 1000;
std::fstream saveCSV;

DWORD WINAPI BleRxThread(LPVOID lpparam);
/*BLE read回调函数*/
VOID CALLBACK FunReadCallBack(void* ParamInf, PCHAR ReadBuf, ULONG ReadBufLen)
{
	g_blerecvcmutex.lock();
	memcpy(&g_blerecvdata[g_blerecvlen], ReadBuf, ReadBufLen);
	g_blerecvlen += ReadBufLen;
	for (int i = 0; i < ReadBufLen - 19; i++) {
		if ((ReadBuf[i] == 0x55) && (ReadBuf[i + 1] == 0x61)) {
			short tmpx = uint8_t(ReadBuf[i + 15]) << 8 | uint8_t(ReadBuf[i + 14]);
			short tmpy = uint8_t(ReadBuf[i + 17]) << 8 | uint8_t(ReadBuf[i + 16]);
			short tmpz = uint8_t(ReadBuf[i + 19]) << 8 | uint8_t(ReadBuf[i + 18]);
			float x = 180.f * tmpx / 32768;
			float y = 180.f * tmpy / 32768;
			float z = 180.f * tmpz / 32768;
			IMU[0].push(x);
			IMU[1].push(y);
			IMU[2].push(z);
			saveCSV << x << "," << y << "," << z << std::endl;
			//saveCSV << ReadBuf[i + 14]-'0' << "," << ReadBuf[i + 15] - '0' << "," << ReadBuf[i + 16] - '0' << "," << ReadBuf[i + 17] - '0' << "," << ReadBuf[i + 18] - '0' << "," << ReadBuf[i + 19] - '0' << std::endl;
		}
	}
	for (int j = 0; j < 3; j++) {
		while (IMU[j].size() > MAXLEN)
			IMU[j].pop();
	}
	g_blerecvcmutex.unlock();
	SetEvent(g_recvevent);

}
int main()
{
	WCHBLEInit();
	saveCSV.open("angle.csv", std::ios::ate | std::ios::out);
	g_recvevent = CreateEvent(NULL, FALSE, FALSE, NULL);
	CloseHandle(CreateThread(NULL, 0, BleRxThread, NULL, 0, NULL));			//创建蓝牙接收文件线程
	Support = WCHBLEIsLowEnergySupported();
	if (!Support) {
		MessageBox(NULL, L"控制器不支持低功耗蓝牙!", L"WCHBleDemo", MB_ICONERROR);
	}
	Support = WCHBLEIsBluetoothOpened();
	if (!Support) {
		MessageBox(NULL, L"请打开系统蓝牙以确保正常使用！", L"WCHBleDemo", MB_ICONERROR);
	}

	int scanTimes = 1000, scannum = 20, listcount = 0;
	char DevIDFilter[100] = "";
	CHAR bleMac[100] = "";
	PCHAR mactemp = NULL;
	memset(g_BLEDev, 0, sizeof(g_BLEDev));
	WCHBLEEnumDevice(scanTimes, DevIDFilter, g_BLEDev, (ULONG*)&scannum);
	for (int i = 0; i < scannum; ++i) {
		std::cout << "Found BLE device: " << (char*)g_BLEDev[i].Name << "," << (char*)g_BLEDev[i].DevID << std::endl;
		char* p1 = strstr((char*)g_BLEDev[i].Name, "WTwisemen");
		if (p1 == NULL)
			std::cout << "Cannot found WTwisemen" << std::endl;
		else {
			memcpy(g_blename, g_BLEDev[i].Name, 100);
			memcpy(g_blepath, g_BLEDev[i].DevID, 100);
			std::cout << "Found WTwisemen: " << g_blename << "," << g_blepath << std::endl;
			break;
		}
		listcount++;
	}

	if (g_devhandle != NULL) {
		WCHBLECloseDevice(g_devhandle);
		g_devhandle = NULL;
	}
	g_devhandle = WCHBLEOpenDevice(g_blepath, NULL);
	if (g_devhandle == NULL) {
		MessageBox(NULL, L"打开设备失败！", L"WCHBleDemo", MB_ICONWARNING);
		return 1;
	}
	else {
		std::cout << "WCHBLEOpenDevice WTwisemen success" << std::endl;
	}

	{
		int pUUIDArryLen = 20, ret = 0;
		ret = WCHBLEGetAllServicesUUID(g_devhandle, g_serviceUUID, (USHORT*)&pUUIDArryLen);
		if (ret != 0) {
			MessageBox(NULL, L"获取服务失败！", L"WCHBleDemo", MB_ICONWARNING);
			return 2;
		}
		for (int i = 0; i < pUUIDArryLen; ++i)
			printf("g_serviceUUID = %#x\n", g_serviceUUID[i]);
		ret = WCHBLEGetMtu(g_devhandle, (USHORT*)&g_MTU);
		if (ret != 0) {
			MessageBox(NULL, L"获取服务失败！", L"WCHBleDemo", MB_ICONWARNING);
			return 2;
		}
		std::cout << "g_MTU = " << g_MTU << std::endl;
	}

	{
		int pUUIDArryLen = 20, ret = 0, select = 2;
		ret = WCHBLEGetCharacteristicByUUID(g_devhandle, g_serviceUUID[select], g_characteristicUUID, (USHORT*)&pUUIDArryLen);
		if (ret != 0) {
			MessageBox(NULL, L"获取特征失败！", L"WCHBleDemo", MB_ICONWARNING);
			return 3;
		}
		for (int i = 0; i < pUUIDArryLen; ++i) {
			printf("g_characteristicUUID = %#x\n", g_characteristicUUID[i]);
		}
	}

	{
		int pAction = 0, ret = 0, select1 = 2, select2 = 0;
		ret = WCHBLEGetCharacteristicAction(g_devhandle, g_serviceUUID[select1], g_characteristicUUID[select2], (ULONG*)&pAction);
		if (ret != 0) {
			MessageBox(NULL, L"获取特征支持操作失败！", L"WCHBleDemo", MB_ICONWARNING);
			return 4;
		}
		std::cout << "pAction = " << pAction << std::endl;
	}

	{
		int ret = 0, select1 = 2, select2 = 1;
		g_paramInf[0].DevHandle = g_devhandle;
		g_paramInf[0].CharacteristicUUID = g_characteristicUUID[select2];
		g_paramInf[0].ServiceUUID = g_serviceUUID[select1];
		ret = WCHBLERegisterReadNotify(g_devhandle, g_serviceUUID[select1], g_characteristicUUID[select2], FunReadCallBack, (void*)&g_paramInf[0]);
		if (ret != 0) {
			MessageBox(NULL, L"打开订阅失败！", L"WCHBleDemo", MB_ICONWARNING);
			return 5;
		}
	}


	//int ret = 0, select1 = 2, select2 = 1, readlen = 512;
	//char readbuf[512] = "";
	//int tick = 100;
	//while (tick-- > 0) {
	//	ret = WCHBLEReadCharacteristic(g_devhandle, g_serviceUUID[select1], g_characteristicUUID[select2],
	//		readbuf, (UINT*)&readlen);
	//	if (ret != 0) {
	//		MessageBox(NULL, L"读取特征值失败！", L"WCHBleDemo", MB_ICONWARNING);
	//		return 6;
	//	}
	//	/*printf("readbuf = ");
	//	for(int i=0;i< readlen;i++)
	//		printf("%02X,", readbuf[i]);
	//	printf("\n");*/
	//	for (int i = 0; i < readlen-19; i++) {
	//		if ((readbuf[i] == 0x55) && (readbuf[i+1] == 0x61))
	//			printf("rec readbuf[0]\n", readbuf[13]);
	//	}
	//}
	Sleep(10000);

	saveCSV.close();
	WCHBLECloseDevice(g_devhandle);
	std::cout << "Hello World!\n";
	return 0;
}

///*将char型数据转换成16进制的两个字符*/
//CString Char2Hex(char* pdata, int length)
//{
//	unsigned char* temp = (unsigned char*)malloc(length);
//	CString tmpStr = "", testStr = "";
//
//	memcpy(temp, pdata, length);
//	for (int i = 0; i < length; i++) {
//		testStr.Format("%02X ", temp[i]);
//		tmpStr += testStr;
//	}
//	free(temp);
//	temp = NULL;
//	return tmpStr;
//}
/*
接收线程
接收线程一直都在，在没有接收的时候会等待事件触发
*/
DWORD WINAPI BleRxThread(LPVOID lpparam)
{
	DWORD recvlen = 0;

	while (1) {
		WaitForSingleObject(g_recvevent, INFINITE);
		g_blerecvcmutex.lock();
		memset(g_recvcopybuf, 0, sizeof(g_recvcopybuf));
		memcpy(g_recvcopybuf, g_blerecvdata, g_blerecvlen);
		memset(g_blerecvdata, 0, g_blerecvlen);
		recvlen = g_blerecvlen;
		printf("recvlen = %d\n", recvlen);
		g_blerecvlen = 0;
		g_blerecvcmutex.unlock();
	}
	return 0;
}


// 运行程序: Ctrl + F5 或调试 >“开始执行(不调试)”菜单
// 调试程序: F5 或调试 >“开始调试”菜单

// 入门使用技巧: 
//   1. 使用解决方案资源管理器窗口添加/管理文件
//   2. 使用团队资源管理器窗口连接到源代码管理
//   3. 使用输出窗口查看生成输出和其他消息
//   4. 使用错误列表窗口查看错误
//   5. 转到“项目”>“添加新项”以创建新的代码文件，或转到“项目”>“添加现有项”以将现有代码文件添加到项目
//   6. 将来，若要再次打开此项目，请转到“文件”>“打开”>“项目”并选择 .sln 文件
